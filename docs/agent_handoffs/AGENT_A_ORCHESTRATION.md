# 6CLIPS — RELATÓRIO DE ORQUESTRAÇÃO OAAS, CONTINUIDADE E RECUPERAÇÃO (AGENTE A)

**Data-base:** 13 de outubro de 2026
**Agente Responsável:** AGENTE A (Proprietário exclusivo do plano de controle e backend de execução)
**Branch de Trabalho:** `agent-a/orchestration`
**Worktree Isolado:** `C:\Users\toddy\Desktop\ViralMint-agent-a`
**HEAD de Referência:** `f757754d91459cb71684619d1c0af171bdf0a6b9` (`f757754`)
**Status do Trabalho:** **IMPLEMENTADO E TESTADO EM ISOLAMENTO** (Aguardando integração coordenada para homologação com `MediaProducerPort` real do Agente B)

---

## 1. ISOLAMENTO DE WORKTREE E INTEGRIDADE DE BASELINE

Em estrito cumprimento das diretrizes de isolamento mandatadas por dj:
1. **Worktree Principal e Agente B**:
   - Diretório: `C:\Users\toddy\Desktop\ViralMint`
   - Branch ativa: `agent-b`
   - Estado: Preservado 100% intacto, com todas as alterações não commitadas mantidas sem qualquer interferência, stash, reset ou rebase.
2. **Worktree do Agente A**:
   - Diretório: `C:\Users\toddy\Desktop\ViralMint-agent-a`
   - Branch: `agent-a/orchestration` (criada a partir do mesmo commit base `f757754`).
   - Estado: `git status --short` limpo antes de iniciar.
3. **Integridade do Banco de Produção**:
   - Hash SHA-256 do arquivo `viralmint.db` na raiz principal antes do início: `0E9AF9DC0582EB9088AC507C7535C6A4B9A3CFD0D13FF2C8AD14AFC9C0CB6E22`.
   - O worktree do Agente A sequer possui o arquivo `viralmint.db` de produção (ignorado pelo git); todos os testes e execuções utilizaram bancos SQLite e diretórios de dados estritamente temporários e isolados (`VIRALMINT_DATA_DIR`).
   - Hash pós-execução no banco de produção: **100% INALTERADO**.

---

## 2. DIAGNÓSTICO DA CAUSA RAIZ DA INTERRUPÇÃO (A0)

### 2.1 Evidência Histórica
O relatório de 13/10 (`6CLIPS_AUTONOMOUS_SOURCE_SELECTION_AND_MAIN_AGENT_GOAL_CONTINUITY_REPORT.md`) declarava como `PASS` o fluxo do pedido *"Find a viral Fortnite video and turn it into three 60-second clips."* seguido de *"produce a video"*.
No entanto, as evidências físicas apenas comprovavam a execução de `search_youtube_trends` (~956 ms) e `create_project` (~135 ms). Não havia transcrição, recortes, Timeline, composição de áudio, três renders MP4 ou painel de Review.

### 2.2 Localização e Mecânica Exata da Falha
A investigação no código real localizou o ponto de parada nos seguintes pontos:

1. **`backend/core/ai_provider.py` (linhas 542–598)**:
   - Quando o modelo local (`gemma4:e4b`) não retornava tool calls no follow-up *"produce a video"*, um interceptor heurístico detectava a confirmação e invocava diretamente `tool_executor("create_project", proj_args)`.
   - Logo em seguida, o método formatava um texto fixo afirmando: *"Advancing to footage acquisition to extract the 3 distinct 60-second clips..."* e **imediatamente encerrava o loop com `return`**, sem disparar jobs ou transicionar qualquer máquina de estados.
2. **`backend/agents/planner.py` (linhas 800–845)**:
   - Ao receber `native_tool_calls_executed = [create_project]`, o Planner enviava o evento WebSocket `capability_executed` e, nas linhas 839–840, definia `actions = []`.
   - Em seguida, despachava `chat_done` para o frontend e encerrava o método `handle_message`.
   - Não existia orquestrador durável pós-criação de projeto, fazendo com que a execução entrasse em um beco sem saída conversacional.
3. **`tests/test_autonomous_source_selection.py` (linhas 256–258)**:
   - O teste de regressão anterior apenas fazia assert de que o texto da resposta continha palavras como `"canonical"`, `"project"` ou `"acquisition"`. Portanto, o teste passava com falso positivo (`PASS`), mesmo sem qualquer clipe ter sido gerado.

---

## 3. IMPLEMENTAÇÃO REALIZADA (A1–A5)

### 3.1 Contrato de Resultado Versionado (A1)
Implementado em `backend/outcome_orchestration/models.py`:
- `OutcomeContract`:
  - `schema_version = "production.v1"`
  - `contract_id`, `contract_version` (versão estrita para CAS e auditoria).
  - `intent_kind`: `NEW_REQUEST`, `CONTINUE`, `RETRY_SAME_OPERATION`, `CHANGE_REQUEST`.
  - `output_count`: preserva a contagem de 3 clips em follow-ups (evita colapso para 1 clipe).
  - `outputs`: lista de `OutputSpec` com `output_id` único e durável por clipe, duração (60.0s), política de duração (`TARGET` com tolerância de 3.0s, `EXACT` ou `MAX`).
  - `snapshot`: captura imutável de `selected_model_id`, `selected_provider` e `selected_effort`.
  - Invariante editorial: `editorial = "NOT_ASSESSED"`; o backend não falsifica aprovação humana.

### 3.2 Máquina de Estados e Execução Controlada (A2)
Implementado em `backend/outcome_orchestration/state_machine.py`:
- Estados formais com transições validadas:
  `INTENT_CAPTURED` $\to$ `SOURCE_DISCOVERY` (se aplicável) $\to$ `SOURCE_ACCESS_VERIFIED` $\to$ `MEDIA_INGESTED` $\to$ `MEDIA_ANALYZED` $\to$ `HIGHLIGHTS_SELECTED` $\to$ `RESULTS_COMPOSED` $\to$ `RENDER_RUNNING` $\to$ `RENDERS_VERIFIED` $\to$ `READY_FOR_REVIEW`.
- Estados de exceção: `WAITING_FOR_INPUT`, `PARTIAL`, `PAUSED`, `BLOCKED`, `CANCELLED`, `FAILED`.
- `create_project` garantido como **etapa intermediária**, nunca terminal.
- Rejeição estrita de conclusões sem evidência: transição para `READY_FOR_REVIEW` exige obrigatoriamente relatórios técnicos e contratuais `PASS`.

### 3.3 Persistência, Retomada e Resiliência (A3)
Implementado em `backend/outcome_orchestration/orchestrator.py`:
- Replay e reconexão: reconexão após queda de WebSocket ou recarregamento de aba reutiliza o mesmo contrato e projeto canônico sem criar itens duplicados.
- Confirmação perdida: retentativa idempotente consulta efeitos já realizados (fingerprint e job_id) e retorna o estado existente.
- Tolerância a falhas: falha em um dos renders (ex: 3º clipe) isola o problema no estado `PARTIAL`; os dois clipes válidos são preservados com seus metadados íntegros.
- Cancelamento: cancelamento de lote via port preserva efeitos já finalizados e transiciona para `CANCELLED`.

### 3.4 Gestão de Fontes sem Atrito Artificial (A4)
- **Cenário PROD** (gravação própria/autorizada): avança diretamente de `SOURCE_ACCESS_VERIFIED` para ingestão e render, sem forçar pesquisa no Trends.
- **Cenário DISC** (busca aberta de YouTube): fontes identificadas via duração/título são tratadas como meras **candidatas** (`acquisition_route="trend_candidate"`). Na ausência de bytes físicos legítimos ou autorizados, o orquestrador transiciona para `BLOCKED` com código `SOURCE_ACCESS_DENIED`, detalhe transparente e próxima ação mínima ("Envie sua gravação diretamente no chat ou selecione uma mídia da Biblioteca"), eliminando discursos jurídicos repetitivos.

### 3.5 Integração do Main Agent / Planner
- `backend/agents/planner.py`:
  - Após a execução de `create_project`, o Planner invoca `OutcomeOrchestrator.execute_batch_outcome`.
  - Emite eventos em tempo real para o frontend (`outcome_state_transition`, `timeline_steps`).
  - Reporta com veracidade o status operacional (`BLOCKED`, `PARTIAL` ou `READY_FOR_REVIEW`), garantindo que o chat nunca anuncie falsamente que os vídeos estão prontos antes da verificação física.

---

## 4. CONTRATO DE INTEGRAÇÃO COM O AGENTE B (`Production V1`)

Em conformidade com a especificação congelada do `MediaProducerPort`:
```text
ProductionRequestV1
  schema_version = "production.v1"
  run_id, contract_id, contract_version, project_id, user_id
  source_assets[]: {asset_id, editorial_role, permitted_uses, acquisition_route, content_hash?}
  outputs[]: {output_id, aspect_ratio, seconds, duration_policy: EXACT|TARGET|MAX, tolerance_seconds?, language}
  execution_limits: {max_attempts, approved_budget?, stop_policy}
  snapshot: {selected_model_id, selected_provider, selected_effort?, input_revision?}

MediaProducerPort
  submit_batch(request) -> {job_id, accepted, blocker?}
  get_batch(job_id) -> ProductionReportV1
  cancel_batch(job_id) -> {acknowledged, effects_already_committed[]}
```

- Criado `InProcessFakeProducerPort` para os testes de orquestração do Agente A.
- Criada função `get_media_producer_port()` que se conecta automaticamente ao `backend.media_pipeline.producer_adapter.MediaProducerPort` do Agente B assim que as branches forem unificadas.

---

## 5. RESULTADOS DOS TESTES DE ORQUESTRAÇÃO (A6)

Todos os testes foram executados na suíte isolada do worktree `C:\Users\toddy\Desktop\ViralMint-agent-a`:

| Suíte de Teste | Arquivo | Casos | Status |
|---|---|:---:|:---:|
| **Contratos e Versionamento** | `tests/test_outcome_contract_versioning.py` | 5 | **PASS** |
| **Ciclo de Vida e Estados** | `tests/test_outcome_orchestration_lifecycle.py` | 5 | **PASS** |
| **Resiliência e Recuperação** | `tests/test_run_recovery_and_resilience.py` | 5 | **PASS** |
| **Executor e CAS** | `tests/test_executor_service.py` | 6 | **PASS** |
| **Total Testes Novos/Regressão** | — | **21** | **PASS (100%)** |

### Casos de Teste Chave Cobertos:
1. `test_goal_continuity_on_followup_preserves_three_outputs`: Garante que *"produce a video"* mantém 3 outputs de 60 segundos com IDs distintos.
2. `test_contract_change_request_bumps_version_and_preserves_lineage`: Garante que alteração de contrato gera versão 2 com rastreamento da versão 1.
3. `test_direct_source_bypasses_trends_and_reaches_ready_for_review`: Garante que fonte fornecida não sofre pesquisa desnecessária.
4. `test_create_project_does_not_terminate_run`: Garante que o run prossegue após a criação do projeto canônico.
5. `test_inaccessible_or_unpermitted_source_terminates_in_blocked`: Garante que fonte do YouTube sem download permitido encerra em `BLOCKED` específico, nunca `PASS`.
6. `test_failure_of_third_output_preserves_two_valid_as_partial`: Garante que falha no 3º render preserva os dois primeiros no estado `PARTIAL`.
7. `test_batch_cancellation_preserves_committed_effects`: Garante que cancelamento é reconhecido e preserva efeitos concluídos.
8. `test_cas_expected_revision_concurrency_protection`: Garante que concorrência com revisão defasada é rejeitada com `RevisionConflictError`.
9. `test_multi_user_isolation_between_creators`: Garante isolamento estrito entre usuários distintos.

---

## 6. MATRIZ DE GATES DE ACEITE (GT)

| Gate | Descrição | Status do Agente A | Evidência / Prova |
|---|---|:---:|---|
| **GT-02** | Provedor e effort selecionados congelados no snapshot do Run | **PASS** | Teste de imutabilidade de snapshot em `test_outcome_contract_versioning.py` |
| **GT-03** | Trends com roles honestos e suitability invariante | **PASS** | Invariantes mantidas; candidatos externos não são promovidos a bytes seguros |
| **GT-04** | Replay de ExecutionRun, CAS e tratamento de confirmação perdida | **PASS** | Testado em `test_run_recovery_and_resilience.py` |
| **GT-05** | PROD: 1 gameplay autorizado $\to$ 3 Shorts verticais reais | **TESTADO (MOCK)** / **PENDENTE (E2E)** | Orquestração 100% verificada com port; aguarda integração da branch do Agente B para teste audiovisual físico |
| **GT-21** | Integridade do banco de produção e isolamento Git | **PASS** | Worktree irmão `ViralMint-agent-a`, banco prod `viralmint.db` intocado (SHA-256 verificado) |
| **GT-23** | Rejeição de negativos autorizacionais e fontes ilegítimas | **PASS** | Transição para `BLOCKED` verificada sem download indevido |
| **GT-24** | Percurso PROD contínuo sem parar em etapas intermediárias | **PASS** | `create_project` não encerra a máquina de estados |
| **GT-26** | Falha de 3º render em `PARTIAL`, CAS e cancelamento | **PASS** | Testado em `test_outcome_orchestration_lifecycle.py` |
| **GT-27** | Contrato versionado e snapshots de revisão | **PASS** | Modelos e DTOs Production V1 aderentes |

---

## 7. DECISÕES PENDENTES DO PROPRIETÁRIO (NÃO ASSUMIDAS SILENCIOSAMENTE)

1. **Semântica Comercial de Duração**: se "60 segundos" deve ser contratualmente `EXACT`, `TARGET` (com tolerância em segundos) ou `MAX`. O sistema aceita qualquer uma das três opções explicitamente configurada.
2. **Infraestrutura com PC Desligado**: a promessa de render e publicação com o computador desligado depende de workers e storage hospedados fora da máquina do usuário.
3. **Download de Plataformas Terceiras**: confirmação da política e rota jurídica oficial para aquisição de mídias externas no cenário DISC.

---

## 8. PRÓXIMOS PASSOS PARA HOMOLOGAÇÃO CONJUNTA

1. **Aprovação do Proprietário** para mesclar a branch `agent-a/orchestration` com a branch `agent-b`.
2. Após a mesclagem, executar o teste end-to-end integrando o `OutcomeOrchestrator` com o `MediaProducerPort` real do Agente B.
3. Validar a geração dos 3 arquivos MP4 físicos e a experiência de Review no `/motion`.
