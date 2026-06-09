# 队友：恢复 Layer1 dump

1. Docker `docker compose up -d`
2. 下载 `icu_scheduling_layer1_schemas_*.dump`
3. `restore_layer1.ps1 -Target scheduling -DumpFile ...`
4. 配置环境并运行 Streamlit
