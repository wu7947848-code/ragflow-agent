# RAGFlow Agent

A comprehensive testing and evaluation framework for RAGFlow conversational agents. Provides automated test suites, golden evaluation datasets, stress testing, and safety validation for LLM-powered agents.

## Features
- **Automated Testing:** Regression, scenario, boundary, and edge case test suites
- **Golden Evaluation:** Standardized evaluation dataset with automated runner for consistent quality assessment
- **Stress Testing:** Load and performance testing under various conditions
- **Safety Guards:** Content safety and prompt injection detection tests
- **Conversation Tracing:** State machine verification and conversation flow tracking
- **Cross-Fact Validation:** Multi-source fact consistency checking

## Test Suites

| Suite | Description |
|-------|-------------|
| Regression | Core functionality regression tests |
| Scenario | End-to-end user scenario simulation |
| Clarification | Ambiguity handling and clarification tests |
| Safety Guard | Content safety and adversarial input testing |
| Stress | Load testing with concurrent users |
| State Trace | Conversation state machine verification |
| Audit | Audit trail and logging verification |
| Golden Eval | Standardized quality evaluation framework |

## Tech Stack
- **Language:** Python
- **Target:** RAGFlow Agent API
- **LLM:** Claude, GPT for evaluation
- **Data:** JSON-based test cases and evaluation datasets

## Quick Start
