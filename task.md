MiroFish: Full Chinese → English Translation
Frontend Translation
 Batch 1 — Heavy components: 
Step4Report.vue
 (227), 
Process.vue
 (177), Step2EnvSetup.vue (168)
 Batch 2 — Medium components: HistoryDatabase.vue (127), Step5Interaction.vue (89), GraphPanel.vue (87), Step3Simulation.vue (74)
 Batch 3 — Views: 
Home.vue
 (53), SimulationRunView.vue (39), SimulationView.vue (38), ReportView.vue (11), InteractionView.vue (11), MainView.vue (4), App.vue (4)
 Batch 4 — JS/API layer: simulation.js (29), graph.js (10), report.js (8), index.js (8), pendingUpload.js (2)
 Batch 5 — Step1: Step1GraphBuild.vue (12)
Backend Translation
 Batch 6 — Services (heavy): report_agent.py (670), simulation_runner.py (348), oasis_profile_generator.py (315)
 Batch 7 — Services (medium): simulation_config_generator.py (255), zep_tools.py (461), zep_graph_memory_updater.py (159), ontology_generator.py (149)
 Batch 8 — API layer: simulation.py (487), report.py (149), graph.py (114)
 Batch 9 — Models + other services: project.py (50), task.py (37), graph_builder.py (79), zep_entity_reader.py (77), simulation_ipc.py (72), simulation_manager.py (91), text_processor.py (17)
 Batch 10 — Utils + Core: file_parser.py (38), retry.py (35), logger.py (24), llm_client.py (18), config.py (20), __init__.py files, zep_paging.py (6)
Config Files
 Batch 11: pyproject.toml, requirements.txt, package.json
Verification
 Run grep -rP '[\x{4e00}-\x{9fff}]' to confirm zero remaining Chinese characters in source
 Run npm run dev and visually inspect UI pages