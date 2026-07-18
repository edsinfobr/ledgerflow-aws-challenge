# 💰 LedgerFlow - Controle de Fluxo de Caixa Diário

Sistema escalável, resiliente e orientado a eventos para controle de lançamentos de fluxo de caixa (débitos e créditos) e consolidação de saldo diário. Projetado nativamente para a **AWS** seguindo as diretrizes do **AWS Well-Architected Framework**.

---

## 🗺️ 1. Mapeamento de Domínios e Capacidades de Negócio

Aplicando os conceitos de **Domain-Driven Design (DDD)**, o ecossistema foi decomposto nos seguintes domínios:

### Subdomínios e Contextos Delimitados (Bounded Contexts)
*   **Contexto de Lançamentos (Posting Domain):** Domínio Core responsável pela ingestão, validação e persistência imediata de cada movimentação financeira (Crédito/Débito). Prioriza **alta disponibilidade** e **baixa latência**.
*   **Contexto de Consolidação (Consolidation Domain):** Domínio de Suporte responsável por agregar os dados assincronamente e computar o saldo consolidado por dia comercial.

### Capacidades de Negócio (Business Capabilities)
| Capacidade | Input | Processo | Output |
| :--- | :--- | :--- | :--- |
| **Registrar Lançamento** | Valor, Tipo (C/D), Timestamp, ID do Comerciante | Validação de esquema e persistência síncrona. | ID do Lançamento & Status `PENDING` ou `COMMITTED` |
| **Consolidar Saldo Diário** | Eventos de Lançamento | Processamento assíncrono agregador por data. | Razão de Saldos por Dia |
| **Consultar Relatório Diário** | ID do Comerciante, Data | Leitura em cache/banco otimizado para leitura. | Saldo Consolidado Final |

---

## ⚙️ 2. Refinamento de Requisitos

### Requisitos Funcionais (RF)
*   [RF-001] O sistema deve permitir a entrada de lançamentos de débito e crédito.
*   [RF-002] O sistema deve garantir a idempotência no registro de lançamentos para evitar duplicidade.
*   [RF-003] O sistema deve fornecer um relatório descritivo com o saldo diário consolidado por comerciante.

### Requisitos Não-Funcionais (RNF)
*   [RNF-001] **Disponibilidade Isolada:** O serviço de lançamentos **não deve** ficar indisponível se o sistema de consolidado diário falhar.
*   [RNF-002] **Escalabilidade sob Pico:** O serviço de consolidado deve suportar picos de **50 requisições por segundo (RPS)** com perda máxima de 5% (Alvo do projeto: 0% de perda utilizando filas).
*   [RNF-003] **Persistência Poliglota:** Armazenamento otimizado para o caso de uso (Gravação rápida para lançamentos, consultas rápidas para consolidados).

---

## 🏗️ 3. Arquitetura da Solução (Target Architecture)

A solução adota um padrão **Serverless Event-Driven Architecture (Arquitetura Orientada a Eventos)**.