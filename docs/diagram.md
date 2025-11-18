                                      ┌────────────────────────────────────┐
                                      │            USER INPUT              │
                                      │   ("pon B5 en 1000", "sube doc")   │
                                      └────────────────────────────────────┘
                                                      │
                                                      ▼
                          ┌────────────────────────────────────────────────────┐
                          │                    ROUTER ACTIVO                    │
                          │ Intent Detection + Confidence + Examples + Memory   │
                          └────────────────────────────────────────────────────┘
                              │            │              │             │
                              │            │              │             │
                              ▼            ▼              ▼             ▼

                 ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐
                 │ PropertyAgent  │  │ NumbersAgent     │  │ DocsAgent       │  │ MainAgent         │
                 │ Cambiar/crear  │  │ Cálculos R2B     │  │ Upload + Emails │  │ Tareas libres /   │
                 │ propiedad       │ │ Fórmulas         │  │ Generate PDFs   │  │ fallback           │
                 └────────────────┘  └─────────────────┘  └─────────────────┘  └──────────────────┘
                          │                   │                  │                     │
                          └──────────────┬────┴───────┬─────────┴──────────────┬─────┘
                                         │              │                        │
                                         ▼              ▼                        ▼

                           ┌──────────────────┐   ┌──────────────────┐   ┌─────────────────────────┐
                           │  TOOL CONTRACTS  │   │ TOOL EXECUTOR     │   │       VERIFIER          │
                           │  (JSON Schemas)  │   │  (Real actions)   │   │  "¿Funcionó de verdad?" │
                           └──────────────────┘   └──────────────────┘   └─────────────────────────┘
                                         │              │                        │
                                         ▼              ▼                        ▼

                             ┌──────────────────────────────┐
                             │        DATABASE LAYER         │
                             │  - numbers.db (R2B)           │
                             │  - properties.db              │
                             │  - documents/                 │
                             └──────────────────────────────┘
                                         │
                                         ▼

                              ┌──────────────────────────────────┐
                              │  METRICS ENGINE (tools/metrics)  │
                              │  - Latencia                      │
                              │  - Errores                       │
                              │  - Tool calls                    │
                              │  - Health Status                 │
                              └──────────────────────────────────┘
                                         │
                                         ▼

                         ┌───────────────────────────────────────────────┐
                         │       FRONTEND – DASHBOARD DE MÉTRICAS        │
                         │     http://localhost:3000/dev/metrics         │
                         │                                               │
                         │   • Gráficos tiempo real                      │
                         │   • Error Rate                                │
                         │   • Semáforo de salud                         │
                         │   • Tool Calls                                │
                         │   • Latencia P95                              │
                         └───────────────────────────────────────────────┘


