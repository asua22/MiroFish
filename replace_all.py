import os
import glob
import re

rep_dict = {
    # index.html
    'lang="zh-CN"': 'lang="en"',
    '社交媒体舆论模拟系统': 'Social Media Simulation Engine',
    '预测万物': 'Predict Everything',
    
    # Home.vue
    '访问我们的Github主页': 'Visit our GitHub',
    '简洁通用的群体智能引擎': 'Universal Swarm Intelligence Engine',
    'v0.1-预览版': 'v0.1-Preview',
    '上传任意报告 / 即刻推演未来': 'Upload any report / Simulate the future instantly',
    '系统状态': 'System status',
    '准备就绪': 'Ready',
    '低成本': 'Low cost',
    '高可用': 'High availability',
    '工作流序列': 'Workflow',
    '图谱构建': 'Graph Build',
    '环境搭建': 'Environment Setup',
    '开始模拟': 'Start Simulation',
    '报告生成': 'Report Generation',
    '深度互动': 'Deep Interaction',
    '现实种子': 'Reality Seeds',
    '拖拽文件上传': 'Drag and drop files to upload',
    '或点击浏览文件系统': 'Or click to browse file system',
    '输入参数': 'Input Parameters',
    '模拟提示词': 'Simulation Prompt',
    '引擎: MiroFish-V1.0': 'Engine: MiroFish-V1.0',
    '启动引擎': 'Start Engine',
    '初始化中...': 'Initializing...',
    
    # MainView.vue
    "{ graph: '图谱', split: '双栏', workbench: '工作台' }": "{ graph: 'Graph', split: 'Split', workbench: 'Workbench' }",
    
    # Step1GraphBuild.vue
    '本体生成': 'Ontology Generation',
    'GraphRAG构建': 'GraphRAG Build',
    '构建完成': 'Build Complete',
    '已完成': 'Completed',
    '生成中': 'Generating',
    '等待': 'Waiting',
    '进行中': 'In Progress',
    '实体节点': 'Entity Nodes',
    '关系边': 'Relation Edges',
    'SCHEMA类型': 'Schema Types',
    '进入环境搭建 ➝': 'Enter Env Setup ➝',
    
    # Step2EnvSetup.vue
    '模拟实例初始化': 'Simulation Instance Init',
    '生成 Agent 人设': 'Generate Agent Persona',
    '生成双平台模拟配置': 'Gen Dual-Platform Config',
    '初始激活编排': 'Initial Active Orchestration',
    '准备完成': 'Preparation Complete',
    '初始化': 'Initializing',
    '编排中': 'Orchestrating',
    '模拟时长': 'Duration',
    '每轮时长': 'Duration per round',
    '总轮次': 'Total rounds',
    '高峰时段': 'Peak hours',
    '活跃时段': 'Active hours',
    '发帖/时': 'Posts/hour',
    '评论/时': 'Comments/hour',
    '响应延迟': 'Response delay',
    '活跃度': 'Activity level',
    '情感倾向': 'Sentiment bias',
    '影响力': 'Influence',
    '事件外显年龄': 'Age',
    '事件外显性别': 'Gender',
    '国家/地区': 'Country/Region',
    '人设简介': 'Bio',
    '详细人设背景': 'Detailed background',
    '← 返回图谱构建': '← Back to Graph Build',
    '开始双世界并行模拟 ➝': 'Start Dual-World Simulation ➝',
    '模拟轮数设定': 'Simulation Rounds Setting',
    '自定义': 'Custom',
    '推荐': 'Recommended',
    
    # GraphPanel.vue
    '刷新图谱': 'Refresh Graph',
    '最大化/还原': 'Maximize/Restore',
    'GraphRAG长短期记忆实时更新中': 'GraphRAG memory updating in real-time',
    '等待本体生成...': 'Waiting for ontology generation...',
    '图谱数据加载中...': 'Loading graph data...',
    
    # HistoryDatabase.vue
    '推演记录': 'Simulation History',
    '暂无文件': 'No files',
    '个文件': 'files',
    '模拟需求': 'Simulation Requirement',
    '关联文件': 'Related Files',
    '推演回放': 'Simulation Replay',
    '分析报告': 'Analysis Report',
    'Step3「开始模拟」与 Step5「深度互动」需在运行中启动，不支持历史回放': 'Step 3 and Step 5 require running instances and do not support history replay',
    '加载中...': 'Loading...',
}

files_to_check = glob.glob('/home/michael/Escritorio/MiroFish/frontend/src/**/*.vue', recursive=True)
files_to_check.append('/home/michael/Escritorio/MiroFish/frontend/index.html')

for filepath in files_to_check:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for k, v in rep_dict.items():
        new_content = new_content.replace(k, v)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")
