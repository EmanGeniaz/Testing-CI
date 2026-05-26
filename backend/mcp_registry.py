"""
MCP Registry — manages external tool/service connectors.
Users can enable/disable connectors and provide API credentials.
The orchestrator discovers active MCPs and uses them.
"""

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("e_ai.mcp_registry")

# ═══════════════════════════════════════════════════════════════════════════════
#  CONNECTOR CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════════

MCP_CONNECTORS = [
    {
        "id": "canva",
        "name": "Canva",
        "category": "design",
        "icon": "\U0001f3a8",
        "description": "Design reports, hero banners, social cards using Canva's API",
        "status": "available",
        "requires": ["api_key"],
        "config_fields": [
            {"key": "api_key", "label": "Canva API Key", "type": "password", "required": True},
            {"key": "brand_kit_id", "label": "Brand Kit ID", "type": "text", "required": False},
        ],
    },
    {
        "id": "reddit",
        "name": "Reddit",
        "category": "social_media",
        "icon": "\U0001f916",
        "description": "Pull posts and comments from Reddit using the API",
        "status": "available",
        "requires": ["client_id", "client_secret"],
        "config_fields": [
            {"key": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"key": "subreddits", "label": "Default Subreddits", "type": "text", "required": False, "placeholder": "e.g. health,medicine,patients"},
        ],
    },
    {
        "id": "twitter",
        "name": "X / Twitter",
        "category": "social_media",
        "icon": "\U0001d54f",
        "description": "Search and stream tweets via X API v2",
        "status": "available",
        "requires": ["bearer_token"],
        "config_fields": [
            {"key": "bearer_token", "label": "Bearer Token", "type": "password", "required": True},
        ],
    },
    {
        "id": "meta",
        "name": "Meta (Facebook/Instagram)",
        "category": "social_media",
        "icon": "\U0001f4d8",
        "description": "Access public page posts and comments",
        "status": "coming_soon",
        "requires": ["access_token"],
        "config_fields": [
            {"key": "access_token", "label": "Access Token", "type": "password", "required": True},
        ],
    },
    {
        "id": "brandwatch",
        "name": "Brandwatch",
        "category": "social_listening",
        "icon": "\U0001f4e1",
        "description": "Connect to Brandwatch for social listening data",
        "status": "available",
        "requires": ["api_key"],
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
            {"key": "project_id", "label": "Project ID", "type": "text", "required": True},
        ],
    },
    {
        "id": "meltwater",
        "name": "Meltwater",
        "category": "social_listening",
        "icon": "\U0001f4a7",
        "description": "Pull media intelligence data from Meltwater",
        "status": "available",
        "requires": ["api_key"],
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
    },
    {
        "id": "sprinklr",
        "name": "Sprinklr",
        "category": "social_listening",
        "icon": "\U0001f4a6",
        "description": "Unified CXM platform data access",
        "status": "coming_soon",
        "requires": ["api_key"],
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
    },
    {
        "id": "news_api",
        "name": "News API",
        "category": "traditional_media",
        "icon": "\U0001f4f0",
        "description": "Search global news articles and headlines",
        "status": "available",
        "requires": ["api_key"],
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
    },
    {
        "id": "infovision",
        "name": "InfoVision API",
        "category": "internal",
        "icon": "\U0001f52e",
        "description": "Connect to InfoVision's internal data platform",
        "status": "available",
        "requires": ["api_key", "endpoint_url"],
        "config_fields": [
            {"key": "endpoint_url", "label": "API Endpoint URL", "type": "text", "required": True},
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
    },
    {
        "id": "google_trends",
        "name": "Google Trends",
        "category": "research",
        "icon": "\U0001f4c8",
        "description": "Search trend data from Google Trends",
        "status": "coming_soon",
        "requires": [],
        "config_fields": [],
    },
    {
        "id": "claude_design",
        "name": "Claude Design",
        "category": "design",
        "icon": "✨",
        "description": "AI-powered design adjustments — color themes, layout, styling",
        "status": "active",
        "requires": [],
        "config_fields": [],
        "always_enabled": True,
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
#  REGISTRY CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MCPRegistry:
    """Persists connector enabled-state and configuration to a JSON file."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._state: dict = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
            except Exception as exc:
                log.warning("Failed to load MCP config from %s: %s", self.config_path, exc)
                self._state = {}
        else:
            self._state = {}

    def _save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _find_connector(connector_id: str) -> Optional[dict]:
        for c in MCP_CONNECTORS:
            if c["id"] == connector_id:
                return c
        return None

    def _connector_state(self, connector_id: str) -> dict:
        """Return the persisted state dict for a connector (or empty dict)."""
        return self._state.get(connector_id, {})

    def _enrich(self, connector: dict) -> dict:
        """Merge catalogue entry with persisted state for API output."""
        cid = connector["id"]
        state = self._connector_state(cid)
        enriched = {**connector}

        if connector.get("always_enabled"):
            enriched["enabled"] = True
        else:
            enriched["enabled"] = state.get("enabled", False)

        # Include user config (but mask password fields for listing)
        user_config = state.get("config", {})
        safe_config: dict = {}
        for field in connector.get("config_fields", []):
            key = field["key"]
            if key in user_config:
                if field["type"] == "password":
                    # Mask but indicate it was provided
                    safe_config[key] = "********" if user_config[key] else ""
                else:
                    safe_config[key] = user_config[key]
        enriched["user_config"] = safe_config
        return enriched

    # ── public API ───────────────────────────────────────────────────────────

    def list_connectors(self) -> list[dict]:
        """Return all connectors with their enabled/config status."""
        return [self._enrich(c) for c in MCP_CONNECTORS]

    def get_connector(self, connector_id: str) -> dict:
        """Get a specific connector (enriched)."""
        connector = self._find_connector(connector_id)
        if connector is None:
            raise KeyError(f"Connector '{connector_id}' not found")
        return self._enrich(connector)

    def enable_connector(self, connector_id: str, config: dict) -> dict:
        """Enable a connector with the provided config (API keys etc.)."""
        connector = self._find_connector(connector_id)
        if connector is None:
            raise KeyError(f"Connector '{connector_id}' not found")

        if connector.get("status") == "coming_soon":
            raise ValueError(f"Connector '{connector_id}' is coming soon and cannot be enabled yet")

        # Validate required fields
        missing = []
        for field in connector.get("config_fields", []):
            if field.get("required") and not config.get(field["key"]):
                missing.append(field["label"])
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        self._state[connector_id] = {
            "enabled": True,
            "config": config,
        }
        self._save()
        log.info("MCP connector enabled: %s", connector_id)
        return self.get_connector(connector_id)

    def disable_connector(self, connector_id: str) -> dict:
        """Disable a connector (keeps config for re-enabling)."""
        connector = self._find_connector(connector_id)
        if connector is None:
            raise KeyError(f"Connector '{connector_id}' not found")

        if connector.get("always_enabled"):
            raise ValueError(f"Connector '{connector_id}' is always enabled and cannot be disabled")

        if connector_id in self._state:
            self._state[connector_id]["enabled"] = False
        else:
            self._state[connector_id] = {"enabled": False, "config": {}}
        self._save()
        log.info("MCP connector disabled: %s", connector_id)
        return self.get_connector(connector_id)

    def get_active_connectors(self) -> list[dict]:
        """Return only enabled connectors -- used by the orchestrator."""
        return [c for c in self.list_connectors() if c.get("enabled")]

    def test_connector(self, connector_id: str) -> dict:
        """Test if a connector's credentials work (placeholder for now)."""
        connector = self._find_connector(connector_id)
        if connector is None:
            raise KeyError(f"Connector '{connector_id}' not found")

        state = self._connector_state(connector_id)
        if not state.get("enabled"):
            return {
                "connector_id": connector_id,
                "success": False,
                "message": "Connector is not enabled. Enable it first.",
            }

        # Placeholder: in production this would make a real API call.
        config = state.get("config", {})
        has_all_keys = all(
            bool(config.get(field["key"]))
            for field in connector.get("config_fields", [])
            if field.get("required")
        )

        if has_all_keys:
            return {
                "connector_id": connector_id,
                "success": True,
                "message": f"Credentials for {connector['name']} look valid (connectivity test is a placeholder).",
            }
        else:
            return {
                "connector_id": connector_id,
                "success": False,
                "message": "Some required credentials are missing.",
            }


# ═══════════════════════════════════════════════════════════════════════════════
#  SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_registry: Optional[MCPRegistry] = None


def get_mcp_registry() -> MCPRegistry:
    """Return the singleton MCPRegistry, lazily initialised."""
    global _registry
    if _registry is None:
        import os
        data_dir = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
        _registry = MCPRegistry(data_dir / "mcp_config.json")
    return _registry
