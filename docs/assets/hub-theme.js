// Shared with scripts/hub_charts.py; keep the literal JSON for parity checks.
const HUB_THEME = {
  "color": [
    "#1c2d6b",
    "#1a1410",
    "#858a94",
    "#5b6ba8",
    "#3f434a",
    "#b8bcc4"
  ],
  "backgroundColor": "#ffffff",
  "textStyle": {
    "color": "#3f434a"
  },
  "title": {
    "textStyle": {
      "color": "#1a1410"
    }
  },
  "legend": {
    "textStyle": {
      "color": "#3f434a"
    },
    "inactiveColor": "#b8bcc4",
    "borderColor": "#c3c7cf",
    "inactiveBorderColor": "#b8bcc4",
    "pageIconColor": "#1c2d6b",
    "pageIconInactiveColor": "#b8bcc4",
    "pageTextStyle": {
      "color": "#3f434a"
    }
  },
  "tooltip": {
    "backgroundColor": "#ffffff",
    "borderColor": "#c3c7cf",
    "textStyle": {
      "color": "#1a1410"
    },
    "axisPointer": {
      "lineStyle": {
        "color": "#6b7079"
      },
      "crossStyle": {
        "color": "#6b7079"
      }
    }
  },
  "markLine": {
    "lineStyle": {
      "color": "#6b7079"
    },
    "label": {
      "color": "#3f434a"
    }
  },
  "markArea": {
    "itemStyle": {
      "color": "#f4f5f7"
    },
    "label": {
      "color": "#6b7079"
    }
  },
  "dataZoom": {
    "backgroundColor": "#f4f5f7",
    "fillerColor": "#b8bcc4",
    "borderColor": "#c3c7cf",
    "handleStyle": {
      "color": "#1c2d6b"
    }
  },
  "categoryAxis": {
    "axisLine": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisTick": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisLabel": {
      "color": "#6b7079"
    },
    "nameTextStyle": {
      "color": "#3f434a"
    },
    "splitLine": {
      "lineStyle": {
        "color": [
          "#c3c7cf"
        ]
      }
    }
  },
  "valueAxis": {
    "axisLine": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisTick": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisLabel": {
      "color": "#6b7079"
    },
    "nameTextStyle": {
      "color": "#3f434a"
    },
    "splitLine": {
      "lineStyle": {
        "color": [
          "#c3c7cf"
        ]
      }
    }
  },
  "logAxis": {
    "axisLine": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisTick": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisLabel": {
      "color": "#6b7079"
    },
    "nameTextStyle": {
      "color": "#3f434a"
    },
    "splitLine": {
      "lineStyle": {
        "color": [
          "#c3c7cf"
        ]
      }
    }
  },
  "timeAxis": {
    "axisLine": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisTick": {
      "lineStyle": {
        "color": "#c3c7cf"
      }
    },
    "axisLabel": {
      "color": "#6b7079"
    },
    "nameTextStyle": {
      "color": "#3f434a"
    },
    "splitLine": {
      "lineStyle": {
        "color": [
          "#c3c7cf"
        ]
      }
    }
  }
};
echarts.registerTheme('hub', HUB_THEME);
