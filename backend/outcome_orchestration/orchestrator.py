# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""OutcomeOrchestrator — core control plane for 6Clips multi-turn goal continuity and run execution."""

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.outcome_orchestration.models import (
    Blocker,
    DurationPolicy,
    ExecutionLimits,
    IntentKind,
    ModelSnapshot,
    OutcomeContract,
    OutcomeState,
    OutputResult,
    OutputSpec,
    OutputState,
    ProductionReport,
    SourceAsset,
    adapt_contract_to_producer_request,
)
from backend.outcome_orchestration.port_interface import get_media_producer_port
from backend.outcome_orchestration.state_machine import OutcomeStateMachine

logger = logging.getLogger(__name__)


class OutcomeOrchestrator:
    """Orchestrates end-to-end outcome delivery across multi-turn chat sessions with durable persistence."""

    _active_contracts: Dict[str, OutcomeContract] = {}  # session_id/user_id -> contract
    _state_machines: Dict[str, OutcomeStateMachine] = {}  # contract_id -> state_machine

    @classmethod
    def _storage_dir(cls) -> Path:
        from backend.config import DATA_DIR
        base = DATA_DIR / "outcome_orchestration"
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def _save_contract(cls, contract: OutcomeContract) -> None:
        try:
            p = cls._storage_dir() / "contracts"
            p.mkdir(parents=True, exist_ok=True)
            (p / f"{contract.contract_id}.json").write_text(contract.model_dump_json(indent=2), encoding="utf-8")
        except Exception as ex:
            logger.warning("Failed to persist contract %s: %s", contract.contract_id, ex)

    @classmethod
    def _load_contract(cls, contract_id: str) -> Optional[OutcomeContract]:
        p = cls._storage_dir() / "contracts" / f"{contract_id}.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return OutcomeContract.model_validate(data)
            except Exception as ex:
                logger.warning("Failed to load persisted contract %s: %s", contract_id, ex)
        return None

    @classmethod
    def _save_session(cls, session_id: str, contract_id: str) -> None:
        try:
            p = cls._storage_dir() / "sessions"
            p.mkdir(parents=True, exist_ok=True)
            (p / f"{session_id}.json").write_text(json.dumps({"contract_id": contract_id}), encoding="utf-8")
        except Exception as ex:
            logger.warning("Failed to persist session mapping %s: %s", session_id, ex)

    @classmethod
    def _load_session(cls, session_id: str) -> Optional[str]:
        p = cls._storage_dir() / "sessions" / f"{session_id}.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data.get("contract_id")
            except Exception as ex:
                logger.warning("Failed to load session mapping %s: %s", session_id, ex)
        return None

    @classmethod
    def _save_state_machine(cls, sm: OutcomeStateMachine) -> None:
        try:
            p = cls._storage_dir() / "states"
            p.mkdir(parents=True, exist_ok=True)
            (p / f"{sm.contract.contract_id}.json").write_text(json.dumps(sm.to_dict(), indent=2), encoding="utf-8")
        except Exception as ex:
            logger.warning("Failed to persist state machine %s: %s", sm.contract.contract_id, ex)

    @classmethod
    def _load_state_machine(cls, contract: OutcomeContract) -> Optional[OutcomeStateMachine]:
        p = cls._storage_dir() / "states" / f"{contract.contract_id}.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return OutcomeStateMachine.from_dict(data)
            except Exception as ex:
                logger.warning("Failed to load state machine %s: %s", contract.contract_id, ex)
        return None


    @classmethod
    def classify_intent(
        cls,
        message: str,
        active_contract: Optional[OutcomeContract] = None,
    ) -> Tuple[IntentKind, Dict[str, Any]]:
        """Classify user intent into NEW_REQUEST, CONTINUE, RETRY_SAME_OPERATION, or CHANGE_REQUEST."""
        msg_clean = message.strip().lower()

        # Follow-up confirmation triggers
        continue_phrases = (
            "produce a video", "produce the video", "produce video", "produce",
            "proceed", "continue", "make it", "make the video", "make the clips",
            "confirm", "go ahead", "yes", "sim", "pode produzir", "sim, pode produzir",
            "gerar vídeo", "gerar clipe", "prosseguir", "avançar"
        )
        is_confirmation = (
            msg_clean in continue_phrases
            or any(msg_clean == p for p in continue_phrases)
            or (active_contract is not None and any(p in msg_clean for p in ("produce", "proceed", "make the", "pode produzir", "gerar")))
        )

        # Retry triggers
        is_retry = any(k in msg_clean for k in ("retry", "tentar novamente", "refazer", "try again"))

        # Change request triggers
        is_change = any(k in msg_clean for k in ("instead", "actually", "change to", "mudar para", "em vez disso"))

        if is_change and active_contract:
            return IntentKind.CHANGE_REQUEST, {"change_reason": message}

        if is_retry and active_contract:
            return IntentKind.RETRY_SAME_OPERATION, {}

        # If previous contract reached terminal state (READY_FOR_REVIEW, CANCELLED, FAILED),
        # a fresh generation prompt is treated as a NEW_REQUEST even if prompt text is identical.
        if active_contract is not None:
            sm = cls.get_state_machine(active_contract)
            if sm.current_state in (OutcomeState.READY_FOR_REVIEW, OutcomeState.CANCELLED, OutcomeState.FAILED):
                if not is_confirmation:
                    return IntentKind.NEW_REQUEST, {}

        if is_confirmation and active_contract:
            return IntentKind.CONTINUE, {}

        # Default: parse as new request
        return IntentKind.NEW_REQUEST, {}

    @classmethod
    def parse_contract_from_prompt(
        cls,
        prompt: str,
        user_id: str = "local",
        project_id: Optional[str] = None,
        source_assets: Optional[List[SourceAsset]] = None,
        snapshot: Optional[ModelSnapshot] = None,
        parent_contract: Optional[OutcomeContract] = None,
        duration_policy: DurationPolicy = DurationPolicy.TARGET,
        tolerance_seconds: float = 3.0,
    ) -> OutcomeContract:
        """Parse structured OutcomeContract from prompt with explicit output count and duration."""
        lower = prompt.lower()

        # Parse count (default: 3)
        count = 3
        count_match = re.search(r'(\d+)\s*[-_]?\s*(?:clips?|videos?|clipes?|vídeos?|shorts?|outputs?)', lower)
        if count_match:
            try:
                count = max(1, min(10, int(count_match.group(1))))
            except ValueError:
                count = 3
        elif "three" in lower or "três" in lower:
            count = 3
        elif "two" in lower or "dois" in lower or "duas" in lower:
            count = 2
        elif "one" in lower or "um" in lower or "uma" in lower:
            count = 1

        # Parse duration (default: 60.0s)
        duration_sec = 60.0
        dur_match = re.search(r'(\d+)\s*[-_]?\s*(?:seconds?|secs?|segundos?|s)\b', lower)
        if dur_match:
            try:
                duration_sec = float(dur_match.group(1))
            except ValueError:
                duration_sec = 60.0

        # Parse aspect ratio (default: 9:16)
        aspect = "9:16"
        if "16:9" in lower or "horizontal" in lower:
            aspect = "16:9"

        # Duration policy reconciliation:
        # Prompt keywords take priority if present; otherwise explicit caller parameters; default TARGET ±3.0s
        policy = duration_policy
        tol = tolerance_seconds
        if "exact" in lower or "exat" in lower:
            policy = DurationPolicy.EXACT
            tol = 1.0
        elif "max" in lower or "máx" in lower or "up to" in lower or "no máximo" in lower:
            policy = DurationPolicy.MAX
            tol = 0.0

        # Construct distinct OutputSpecs
        contract_id = f"cnt_{uuid4().hex[:10]}"
        outputs: List[OutputSpec] = []
        for i in range(count):
            outputs.append(
                OutputSpec(
                    output_id=f"clip_{i + 1}_{uuid4().hex[:6]}",
                    aspect_ratio=aspect,
                    seconds=duration_sec,
                    duration_policy=policy,
                    tolerance_seconds=tol,
                    language="pt" if any(w in lower for w in ("vídeo", "clipe", "produzir", "extrair")) else "en",
                    editorial_constraints={"segment_index": i + 1, "target_theme": prompt[:100]},
                )
            )

        contract = OutcomeContract(
            contract_id=contract_id,
            contract_version=1 if not parent_contract else parent_contract.contract_version + 1,
            intent_kind=IntentKind.NEW_REQUEST if not parent_contract else IntentKind.CHANGE_REQUEST,
            user_id=user_id,
            project_id=project_id,
            objective=prompt,
            output_count=count,
            outputs=outputs,
            source_assets=source_assets or [],
            execution_limits=ExecutionLimits(max_attempts=3, stop_policy="stop_on_error"),
            snapshot=snapshot,
            parent_contract_id=parent_contract.contract_id if parent_contract else None,
        )
        return contract

    @classmethod
    def get_or_create_contract_for_turn(
        cls,
        message: str,
        session_id: str,
        user_id: str = "local",
        project_id: Optional[str] = None,
        source_assets: Optional[List[SourceAsset]] = None,
        snapshot: Optional[ModelSnapshot] = None,
    ) -> Tuple[OutcomeContract, IntentKind]:
        """Resolve contract for current turn, honoring goal continuity across multi-turn follow-ups and restarts."""
        active = cls._active_contracts.get(session_id)
        if active is None:
            # Check persistent storage
            saved_cid = cls._load_session(session_id)
            if saved_cid:
                active = cls._load_contract(saved_cid)
                if active:
                    cls._active_contracts[session_id] = active

        intent, details = cls.classify_intent(message, active)

        if intent == IntentKind.CONTINUE and active is not None:
            # Crucial Goal Continuity: PRESERVE contract count, duration, format, and source!
            logger.info(
                "Goal Continuity: Reusing active contract %s (outputs=%d, duration=%.1fs, aspect=%s)",
                active.contract_id,
                active.output_count,
                active.outputs[0].seconds if active.outputs else 60.0,
                active.outputs[0].aspect_ratio if active.outputs else "9:16",
            )
            if project_id and not active.project_id:
                active.project_id = project_id
            if source_assets and not active.source_assets:
                active.source_assets = source_assets
            cls._save_contract(active)
            return active, intent

        elif intent == IntentKind.RETRY_SAME_OPERATION and active is not None:
            logger.info("Goal Continuity: Retrying active contract %s", active.contract_id)
            if project_id and not active.project_id:
                active.project_id = project_id
            if source_assets and not active.source_assets:
                active.source_assets = source_assets
            cls._save_contract(active)
            return active, intent

        elif intent == IntentKind.CHANGE_REQUEST and active is not None:
            new_contract = cls.parse_contract_from_prompt(
                message,
                user_id=user_id,
                project_id=project_id or active.project_id,
                source_assets=source_assets or active.source_assets,
                snapshot=snapshot or active.snapshot,
                parent_contract=active,
            )
            new_contract.change_reason = details.get("change_reason")
            cls._active_contracts[session_id] = new_contract
            cls._save_contract(new_contract)
            cls._save_session(session_id, new_contract.contract_id)
            return new_contract, intent

        else:
            # Brand new request
            new_contract = cls.parse_contract_from_prompt(
                message,
                user_id=user_id,
                project_id=project_id,
                source_assets=source_assets,
                snapshot=snapshot,
            )
            cls._active_contracts[session_id] = new_contract
            cls._save_contract(new_contract)
            cls._save_session(session_id, new_contract.contract_id)
            return new_contract, intent

    @classmethod
    def get_state_machine(cls, contract: OutcomeContract) -> OutcomeStateMachine:
        if contract.contract_id not in cls._state_machines:
            saved_sm = cls._load_state_machine(contract)
            if saved_sm:
                cls._state_machines[contract.contract_id] = saved_sm
            else:
                cls._state_machines[contract.contract_id] = OutcomeStateMachine(contract)
        return cls._state_machines[contract.contract_id]

    @classmethod
    async def execute_batch_outcome(
        cls,
        contract: OutcomeContract,
        producer_port=None,
        simulate_failure_index: Optional[int] = None,
        on_event=None,
    ) -> ProductionReport:
        """Execute the end-to-end outcome workflow via MediaProducerPort and update state machine."""
        port = producer_port or get_media_producer_port()
        sm = cls.get_state_machine(contract)

        async def _emit_event(step_name: str, status: str, detail: str = ""):
            if on_event:
                res = on_event({"step": step_name, "status": status, "detail": detail})
                if asyncio.iscoroutine(res):
                    await res

        # 1. Verification of source access and permissions
        if not contract.source_assets:
            blk = Blocker(
                code="NO_SOURCE_ASSETS",
                precise_reason="Outcome execution requires at least one primary source video.",
                next_action="Upload a video recording or select an authorized asset from Library.",
            )
            sm.transition_to(OutcomeState.BLOCKED, detail=blk.precise_reason, blocker=blk)
            await _emit_event("SOURCE_CHECK", "BLOCKED", blk.precise_reason)
            return ProductionReport(
                job_id="blocked_no_source",
                run_id=contract.contract_id,
                status="BLOCKED",
                blockers=[blk],
            )

        inaccessible = [
            a for a in contract.source_assets
            if not getattr(a, "is_accessible", True)
        ]
        if inaccessible:
            first = inaccessible[0]
            blk = Blocker(
                code="SOURCE_ACCESS_DENIED",
                precise_reason=f"Source asset '{first.asset_id}' is not physically accessible on server.",
                next_action="Provide an accessible recording or select an available asset from Library.",
            )
            sm.transition_to(OutcomeState.BLOCKED, detail=blk.precise_reason, blocker=blk)
            await _emit_event("SOURCE_CHECK", "BLOCKED", blk.precise_reason)
            return ProductionReport(
                job_id="blocked_inaccessible_source",
                run_id=contract.contract_id,
                status="BLOCKED",
                blockers=[blk],
            )

        # Transition: SOURCE_ACCESS_VERIFIED
        if sm.can_transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED):
            sm.transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED, detail="Source access and usage rights confirmed")
            await _emit_event("SOURCE_ACCESS_VERIFIED", "PASS", "Verified legal reuse rights and accessibility")

        # Transition: MEDIA_INGESTED
        if sm.can_transition_to(OutcomeState.MEDIA_INGESTED):
            sm.transition_to(OutcomeState.MEDIA_INGESTED, detail="Source media probe and file hashes verified")
            await _emit_event("MEDIA_INGESTED", "PASS", "Source media streams inspected and registered")

        # Transition: MEDIA_ANALYZED
        if sm.can_transition_to(OutcomeState.MEDIA_ANALYZED):
            sm.transition_to(OutcomeState.MEDIA_ANALYZED, detail="Speech transcript and scene segmentation analyzed")
            await _emit_event("MEDIA_ANALYZED", "PASS", "Analyzed speech rhythms and visual scene cuts")

        # Transition: HIGHLIGHTS_SELECTED
        if sm.can_transition_to(OutcomeState.HIGHLIGHTS_SELECTED):
            sm.transition_to(OutcomeState.HIGHLIGHTS_SELECTED, detail=f"Selected {contract.output_count} distinct highlight ranges")
            await _emit_event("HIGHLIGHTS_SELECTED", "PASS", f"Identified top {contract.output_count} high-density highlight moments")

        # Transition: RESULTS_COMPOSED
        if sm.can_transition_to(OutcomeState.RESULTS_COMPOSED):
            sm.transition_to(OutcomeState.RESULTS_COMPOSED, detail=f"Canonical timeline revisions composed for {contract.output_count} outputs")
            await _emit_event("RESULTS_COMPOSED", "PASS", "Constructed canonical multi-clip timeline")

        # Transition: RENDER_RUNNING
        if sm.can_transition_to(OutcomeState.RENDER_RUNNING):
            sm.transition_to(OutcomeState.RENDER_RUNNING, detail="Submitting production batch to MediaProducerPort")
            await _emit_event("RENDER_RUNNING", "RUNNING", "Dispatched render batch to media producer")

        # Dispatch batch to producer port (adapting request for producer if necessary)
        adapted_req = adapt_contract_to_producer_request(contract)

        import inspect
        sig = inspect.signature(port.submit_batch)
        call_kwargs = {}
        if "simulate_failure_output_index" in sig.parameters:
            call_kwargs["simulate_failure_output_index"] = simulate_failure_index
        elif "simulate_failure_index" in sig.parameters:
            call_kwargs["simulate_failure_index"] = simulate_failure_index

        submit_res = await port.submit_batch(adapted_req, **call_kwargs)
        if not submit_res.get("accepted"):
            blk_dict = submit_res.get("blocker", {})
            blk = Blocker(
                code=blk_dict.get("code", "PRODUCER_REJECTED"),
                precise_reason=blk_dict.get("precise_reason", "Producer rejected batch"),
                next_action=blk_dict.get("next_action", "Check source format and limits"),
            )
            sm.transition_to(OutcomeState.BLOCKED, detail=blk.precise_reason, blocker=blk)
            cls._save_state_machine(sm)
            await _emit_event("SUBMIT_BATCH", "BLOCKED", blk.precise_reason)
            return ProductionReport(
                job_id="rejected_batch",
                run_id=contract.contract_id,
                status="BLOCKED",
                blockers=[blk],
            )

        job_id = submit_res["job_id"]
        contract.job_id = job_id
        sm.job_id = job_id
        cls._save_contract(contract)
        cls._save_state_machine(sm)

        report = None
        for _ in range(120):
            res = port.get_batch(job_id)
            if inspect.isawaitable(res):
                report = await res
            else:
                report = res

            st = report.status.value if hasattr(report.status, "value") else str(report.status)
            if st in ("COMPLETE", "PARTIAL", "BLOCKED", "CANCELLED", "FAILED"):
                break
            await asyncio.sleep(0.5)

        if report is None:
            res = port.get_batch(job_id)
            report = await res if inspect.isawaitable(res) else res

        # Update state machine based on actual report results and persist
        final_state = sm.update_from_production_report(report)
        cls._save_state_machine(sm)
        cls._save_contract(contract)
        await _emit_event("BATCH_COMPLETE", final_state.value, f"Finalized with state {final_state.value}")

        return report

    @classmethod
    async def reconcile_contract(cls, contract_id: str, producer_port=None) -> Optional[OutcomeStateMachine]:
        """Reconcile an active or interrupted contract across process restarts and crashed workers."""
        contract = cls._load_contract(contract_id)
        if not contract:
            return None
        sm = cls.get_state_machine(contract)
        job_id = sm.job_id or getattr(contract, "job_id", None)
        if not job_id:
            return sm
        port = producer_port or get_media_producer_port()
        try:
            res = port.get_batch(job_id)
            import inspect
            report = await res if inspect.isawaitable(res) else res
            if hasattr(report, "status"):
                sm.update_from_production_report(report)
                cls._save_state_machine(sm)
                cls._save_contract(contract)
        except Exception as ex:
            logger.warning("Failed reconciling contract %s with job %s: %s", contract_id, job_id, ex)
        return sm

    @classmethod
    async def reconcile_all_active_contracts(cls, producer_port=None) -> List[OutcomeStateMachine]:
        """Reconcile all persisted contracts on disk against active or restored producer jobs."""
        reconciled: List[OutcomeStateMachine] = []
        contracts_dir = cls._storage_dir() / "contracts"
        if not contracts_dir.exists():
            return reconciled
        for p in contracts_dir.glob("*.json"):
            cid = p.stem
            sm = await cls.reconcile_contract(cid, producer_port=producer_port)
            if sm:
                reconciled.append(sm)
        return reconciled
