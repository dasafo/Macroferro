# 🤖 AI Chatbot for B2B – Macroferro Industrial Sales Assistant

> *From vague product queries to automated invoices – how I built a conversation-driven wholesale platform with FastAPI, OpenAI & Telegram Bot API.*

## 1. 🎯 Why This Project?
Industrial wholesalers often rely on phone calls or PDF catalogues to take orders. This process is slow, error-prone and only works during office hours. **Macroferro** demonstrates that an AI-powered chatbot can take over the entire sales funnel – from product discovery to checkout – while integrating seamlessly with existing inventory and ERP systems.

*Tech-wise, the goal was to combine modern async Python tooling with state-of-the-art NLP to create a production-ready backend.*

## 2. ⚡ Key Features at a Glance
| Capability | Description |
|------------|-------------|
| 🔍 **Semantic Search** | Vector embeddings in Qdrant let the bot understand "I need something to fasten wood" and suggest the right screws. |
| 🛒 **Full Cart Logic** | Users add, remove or update quantities in natural language or via slash commands. |
| 🧠 **Contextual Understanding** | Phrases like "tell me about the 2nd one" are resolved against the last search result list. |
| 🏷️ **Customer Recognition** | Returning clients get autofilled checkout forms and personalised suggestions. |
| 📄 **Automatic Invoicing** | The backend generates PDF invoices and emails them via SendGrid. |
| ☁️ **Cloud-Native Stack** | Dockerised FastAPI backend, PostgreSQL, Redis and Qdrant – ready for any cloud. |

## 3. 🏗️ Architecture Overview

> **Handlers everywhere.** The bot logic is split into `ProductHandler`, `CartHandler`, `CheckoutHandler` and an `AIAnalyzer` that interprets every message with GPT-4o.

### 3.1 🔧 Detailed Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    🌐 PRESENTATION LAYER                    │
├─────────────────────────────────────────────────────────────┤
│  📱 Telegram Bot Interface                                  │
│  └── Webhook endpoints (/webhook)                          │
│  └── Bot commands & message handlers                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      🚪 API LAYER                          │
├─────────────────────────────────────────────────────────────┤
│  🔗 FastAPI REST Endpoints                                 │
│  ├── /api/v1/chat/* (conversation endpoints)               │
│  ├── /api/v1/cart/* (shopping cart operations)             │
│  ├── /api/v1/products/* (product management)               │
│  └── /api/v1/clients/* (customer management)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   🧠 BUSINESS LOGIC LAYER                  │
├─────────────────────────────────────────────────────────────┤
│  🤖 Bot Components (Handlers)                              │
│  ├── ProductHandler (search, info, categories)             │
│  ├── CartHandler (add, remove, update quantities)          │
│  ├── CheckoutHandler (order processing, invoices)          │
│  └── AIAnalyzer (intent detection, NLP)                    │
│                                                             │
│  📄 Business Services                                       │
│  ├── PDF Generation (invoices, reports)                    │
│  ├── Email Service (SendGrid integration)                  │
│  ├── Vector Search (Qdrant operations)                     │
│  └── Background Tasks (async processing)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   💾 DATA ACCESS LAYER                     │
├─────────────────────────────────────────────────────────────┤
│  📝 CRUD Operations                                         │
│  ├── product_crud.py (product operations)                  │
│  ├── client_crud.py (customer management)                  │
│  ├── conversation_crud.py (chat context, recent products)  │
│  └── cart_crud.py (shopping cart persistence)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  🗄️ PERSISTENCE LAYER                      │
├─────────────────────────────────────────────────────────────┤
│  🐘 PostgreSQL (Primary Database)                          │
│  ├── Products, Categories, Clients                         │
│  ├── Orders, Order Items                                   │
│  └── Conversations, Messages                               │
│                                                             │
│  ⚡ Redis (Cache & Session Store)                          │
│  ├── User contexts & conversation state                    │
│  ├── Shopping carts (temporary data)                       │
│  └── Recent products cache                                 │
│                                                             │
│  🔍 Qdrant (Vector Database)                               │
│  ├── Product embeddings (OpenAI)                           │
│  └── Semantic search index                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 🔌 INTEGRATION LAYER                       │
├─────────────────────────────────────────────────────────────┤
│  🤖 OpenAI API                                             │
│  ├── GPT-4o (intent detection, NLP)                        │
│  └── text-embedding-3-small (product vectorization)        │
│                                                             │
│  📧 SendGrid API                                            │
│  └── Email delivery (invoices, notifications)              │
│                                                             │
│  📱 Telegram Bot API                                        │
│  └── Message handling, webhooks                            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 📊 Data Flow Between Layers

1. **📱 User message** → Telegram webhook
2. **🚪 API endpoint** receives and validates request  
3. **🧠 AIAnalyzer** processes intent with GPT-4o
4. **🧠 Specialized handler** executes business logic
5. **💾 CRUD operations** handle data access
6. **🗄️ Database queries** across PostgreSQL/Redis/Qdrant
7. **🔌 External APIs** called when needed (OpenAI/SendGrid)
8. **🧠 Response generation** creates appropriate reply
9. **🚪 JSON response** returned via FastAPI
10. **📱 Message delivery** through Telegram Bot API

This layered architecture ensures **separation of concerns**, **testability**, and **scalability** – each layer has a single responsibility and can be modified independently.

## 4. 🎬 Demo Walk-Through
### 4.1 👤 New Customer Journey  
*Click to enlarge GIFs*  

1. **Product Discovery**  
   ![GIF – search flow](assets/blog/search_flow.gif)
2. **Adding & Updating Cart**  
   ![GIF – cart flow](assets/blog/cart_flow.gif)
3. **Guided Checkout**  
   ![Screenshot – checkout questions](assets/blog/checkout_questions.png)
4. **Generated Invoice PDF**  
   ![Screenshot – invoice](assets/blog/invoice_preview.png)

### 4.2 🔄 Returning Customer Journey
![GIF – returning customer](assets/blog/returning_customer.gif)

### 4.3 💾 Behind the Scenes - Database Operations
*Real system data powering the conversational experience*

![PostgreSQL Tables](assets/blog/postgresql_overview.png)  
*PgAdmin showing 200+ products, categories, and processed orders*

![Qdrant Vector Dashboard](assets/blog/qdrant_collection.png)  
*Vector database with semantic search index - enabling "I need screws for wood" queries*

![Redis Cache Data](assets/blog/redis_cart_data.png)  
*Live shopping cart and user context stored in Redis*

*All flows are captured step-by-step in [docs/FLUJO_INTERACCION.md](./FLUJO_INTERACCION.md).*  

## 5. 🔧 System Deep Dive

### 5.1 💾 Data Layer in Action
*From conversation to database - here's how data flows through the system:*

#### PostgreSQL - Structured Data
![PostgreSQL Schema](assets/blog/postgresql_tables_detail.png)  
*Relational data: Products → Categories → Orders → Clients with real production data*

#### Qdrant - Semantic Search Engine  
![Qdrant Dashboard](assets/blog/qdrant_vectors_detail.png)  
*200 product embeddings with search metrics - powering natural language understanding*

#### Redis - Session Management
![Redis Keys](assets/blog/redis_session_data.png)  
*Real-time cart state and conversation context for seamless user experience*

### 5.2 🚀 API Layer
![FastAPI Documentation](assets/blog/swagger_endpoints.png)  
*25+ REST endpoints with automatic OpenAPI documentation and interactive testing*

### 5.3 🧠 NLP Pipeline
1. **Intent Detection** – open-domain prompt with few-shot examples.
2. **Entity Extraction** – regular expressions + GPT correction.
3. **Fallback Logic** – keyword match and semantic search if GPT is uncertain.

### 5.4 🚀 DevOps & Infrastructure
![Docker Services](assets/blog/docker_compose_running.png)  
*All services orchestrated with Docker Compose - ready for any cloud deployment*

* **🐳 Docker Compose**, Makefile targets for everyday tasks.
* **⚙️ GitHub Actions CI**: Ruff, Black, MyPy, PyTest.
* **🪝 Pre-commit hooks** keep the repo clean.

## 6. 🚧 Challenges & Lessons Learned

* **Resolving "the 4th one."** Index preservation in recent results required a custom batch insert to Redis.

![Redis Implementation](assets/blog/redis_context_solution.png)  
*How we solved context preservation with Redis hash structures*

* **Asynchronous Background Jobs.** PDF generation + email must NOT reuse FastAPI DB sessions – fixed by spawning fresh connections.

![Database Session Management](assets/blog/async_session_pattern.png)  
*Proper async session handling in background tasks*

* **Prompt Robustness.** Small prompt tweaks ("If you are not 80 % confident, ask back") improved accuracy significantly.

![Search Accuracy Metrics](assets/blog/semantic_search_performance.png)  
*Search accuracy improvements: 65% → 85% with prompt engineering*

## 7. 📋 Roadmap
* 💳 Stripe payments integration.
* 📊 Admin dashboard (React) for inventory & orders.
* 🌍 Multilingual support (Spanish/English).

## 8. 📍 Repository & Live Demo
* **💻 Code:** <https://github.com/dasafo/macroferro>
* **🤖 Demo Bot:** `@MacroferroBot` (send *"Need titanium screws"* to start)

## 9. 🔮 What's Next?
I'm exploring how to plug this bot directly into ERP systems so that stock levels stay in sync in real time.  

> *Questions? Feedback? Ping me on [LinkedIn](https://www.linkedin.com/in/dasafodata/) – I'd love to chat about conversational commerce!*
