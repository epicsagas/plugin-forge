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
        "path": "./"
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
