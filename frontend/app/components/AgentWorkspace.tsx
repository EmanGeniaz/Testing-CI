/**
 * AgentWorkspace — the per-tab agent UI.
 *
 * Implementation lives in AgentInspectorModal.tsx (kept for git-history
 * continuity). The modal wrapper has been removed; the component now
 * renders as an inline workspace card sized to `calc(100vh - 130px)`.
 */
export { default, type AgentOption, type TabStatus } from "./AgentInspectorModal";
