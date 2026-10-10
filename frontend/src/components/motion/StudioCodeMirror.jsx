// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useRef, useEffect, memo } from "react"
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from "@codemirror/view"
import { EditorState, Annotation } from "@codemirror/state"
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands"
import { bracketMatching, foldGutter, indentOnInput } from "@codemirror/language"
import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete"
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search"
import { html } from "@codemirror/lang-html"
import { css } from "@codemirror/lang-css"
import { javascript } from "@codemirror/lang-javascript"
import { json } from "@codemirror/lang-json"
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language"
import { tags as t } from "@lezer/highlight"

// Tag programmatic external syncs so user keystroke handlers don't loop
const ExternalSync = Annotation.define()

const customHighlightStyle = HighlightStyle.define([
  { tag: t.keyword, color: "#8b5cf6", fontWeight: "600" },
  { tag: [t.name, t.deleted, t.character, t.propertyName, t.macroName], color: "#1e293b" },
  { tag: [t.function(t.variableName), t.labelName], color: "#2563eb" },
  { tag: [t.color, t.constant(t.name), t.standard(t.name)], color: "#d97706" },
  { tag: [t.definition(t.name), t.separator], color: "#0f172a" },
  { tag: [t.typeName, t.className, t.number, t.changed, t.annotation, t.modifier, t.self, t.namespace], color: "#059669" },
  { tag: [t.operator, t.operatorKeyword, t.url, t.escape, t.regexp, t.link, t.special(t.string)], color: "#db2777" },
  { tag: [t.meta, t.comment], color: "#94a3b8", fontStyle: "italic" },
  { tag: t.strong, fontWeight: "bold" },
  { tag: t.emphasis, fontStyle: "italic" },
  { tag: t.strikethrough, textDecoration: "line-through" },
  { tag: t.link, color: "#2563eb", textDecoration: "underline" },
  { tag: t.heading, fontWeight: "bold", color: "#1e293b" },
  { tag: [t.atom, t.bool, t.special(t.variableName)], color: "#7c3aed" },
  { tag: [t.processingInstruction, t.string, t.inserted], color: "#16a34a" },
  { tag: t.invalid, color: "#dc2626" },
])

const editorTheme = EditorView.theme({
  "&": {
    height: "100%",
    color: "#0f172a",
    backgroundColor: "#ffffff",
    fontSize: "13px",
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  },
  ".cm-scroller": {
    overflow: "auto",
    fontFamily: "inherit",
  },
  ".cm-content": {
    caretColor: "#8b5cf6",
    padding: "8px 0",
  },
  ".cm-cursor, .cm-dropCursor": {
    borderLeftColor: "#8b5cf6",
    borderLeftWidth: "2px",
  },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "#ede9fe",
  },
  ".cm-activeLine": {
    backgroundColor: "#f8fafc",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "#f1f5f9",
    color: "#475569",
    fontWeight: "700",
  },
  ".cm-gutters": {
    backgroundColor: "#f8fafc",
    color: "#94a3b8",
    borderRight: "1px solid #e2e8f0",
  },
  ".cm-matchingBracket": {
    backgroundColor: "#ddd6fe",
    outline: "1px solid #8b5cf6",
  },
  ".cm-searchMatch": {
    backgroundColor: "#fef08a",
    outline: "1px solid #eab308",
  },
  ".cm-searchMatch.cm-searchMatch-selected": {
    backgroundColor: "#fde047",
    outline: "2px solid #ca8a04",
  },
})

function getLanguageExtension(filePath = "") {
  const ext = filePath.split(".").pop()?.toLowerCase() || ""
  switch (ext) {
    case "html":
    case "htm":
      return html()
    case "css":
      return css()
    case "js":
    case "jsx":
    case "ts":
    case "tsx":
      return javascript({ jsx: true, typescript: ext.includes("ts") })
    case "json":
      return json()
    default:
      return html()
  }
}

export const StudioCodeMirror = memo(function StudioCodeMirror({
  content = "",
  filePath = "index.html",
  onChange,
  readOnly = false,
}) {
  const containerRef = useRef(null)
  const editorRef = useRef(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!containerRef.current) return

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const isExternal = update.transactions.some((tr) => tr.annotation(ExternalSync))
        if (!isExternal && onChangeRef.current) {
          onChangeRef.current(update.state.doc.toString())
        }
      }
    })

    const startState = EditorState.create({
      doc: content,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        foldGutter(),
        history(),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        highlightActiveLine(),
        highlightSelectionMatches(),
        getLanguageExtension(filePath),
        syntaxHighlighting(customHighlightStyle, { fallback: true }),
        editorTheme,
        keymap.of([
          ...closeBracketsKeymap,
          ...defaultKeymap,
          ...searchKeymap,
          ...historyKeymap,
        ]),
        updateListener,
        EditorState.readOnly.of(readOnly),
      ],
    })

    const view = new EditorView({
      state: startState,
      parent: containerRef.current,
    })

    editorRef.current = view

    return () => {
      view.destroy()
      editorRef.current = null
    }
  }, [filePath, readOnly])

  // Sync external content changes into the editor without resetting cursor when matching
  useEffect(() => {
    const view = editorRef.current
    if (!view) return

    const currentDoc = view.state.doc.toString()
    if (content !== currentDoc) {
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: content },
        annotations: ExternalSync.of(true),
      })
    }
  }, [content])

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        overflow: "hidden",
        position: "relative",
      }}
    />
  )
})

export default StudioCodeMirror
