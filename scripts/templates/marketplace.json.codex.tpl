{
  "name": "__NAME__",
  "interface": {
    "displayName": "__DISPLAYNAME__"
  },
  "plugins": [
    {
      "name": "__NAME__",
      "description": "__DESC__",
      "source": {
        "source": "local",
        "path": "./plugins/__NAME__"
      },
      "pluginManifest": "./.codex-plugin/plugin.json",
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
