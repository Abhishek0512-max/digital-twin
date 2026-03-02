# Projects

## DocSense — RAG Search Assistant
**Timeline:** October 2025 – Present

I'm building a Retrieval Augmented Generation (RAG) search assistant designed for research papers and engineering handbooks. The system uses chunking, embeddings, vector search, hybrid retrieval, and grounded LLM answering to surface precise answers from technical documents.

A key part of this project is the evaluation layer. I'm designing an LLM-as-Judge evaluation harness to score retrieval quality, grounding fidelity, and hallucination severity. The RAG evaluation pipeline measures retrieval precision, chunk quality, reranking performance, and context-window sensitivity.

This project reflects what I care about most — building retrieval systems that are not just functional but measurably good, with clear evaluation criteria and continuous improvement loops.

## Automated Lung Disease Prediction
**Timeline:** January 2023 – May 2023

I built a deep learning-powered diagnostic system to classify chest X-rays for diseases such as COVID-19 and Pneumonia. The system achieved over 90% accuracy using models including VGG16, ResNet50, InceptionV3, and Xception.

I applied data preprocessing, normalization, and augmentation on a dataset of 21,000+ X-ray images, optimizing performance across multiple CNN architectures. This project taught me a lot about working with real medical imaging data and the importance of robust evaluation when the stakes are high.

## AI Agent for LLM Security Log Analysis (at Juume AI)

This was my favorite project. I built an AI agent that analyzes LLM usage logs to detect sensitive-data leakage. The system uses RAG over internal DLP rules, API policies, secrets dictionaries, and past incidents.

What made it special was the combination of everything I care about: security, LLMs, infrastructure, vector search, and real-world impact. It wasn't just "build a model" — it was design ingestion pipelines, structure logs, create embeddings over DLP rules, build a reasoning layer, and trigger actionable alerts.

The agent classifies each event as Safe, Warning, or Violation with LLM reasoning, and uses tool-calling to open alerts and escalate high-risk leakage events automatically. It felt like building something that could exist in a real SOC tomorrow.
