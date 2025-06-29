# Building an AI-Powered B2B Sales Assistant: From Concept to Production

*How I developed a conversational commerce platform that transforms industrial ordering from phone calls to automated invoices*

## The Problem: B2B Commerce Stuck in the Past

Industrial wholesalers are still operating like it's 1995. Picture this: a customer needs specific screws for a construction project. They call during business hours, describe what they need over the phone, wait for quotes via email, call back to place orders, and receive invoices days later.

This manual process is:
- **Slow**: Multiple touchpoints and delays
- **Error-prone**: Miscommunication leads to wrong orders  
- **Limited**: Only available during office hours
- **Inefficient**: Requires dedicated sales staff for simple queries

Meanwhile, B2C e-commerce has evolved to offer instant search, personalized recommendations, and one-click purchasing. Why should B2B be any different?

## The Solution: Macroferro AI Sales Assistant

I set out to build **Macroferro** – an AI-powered Telegram chatbot that handles the entire sales funnel from product discovery to invoice generation. The goal was simple: enable customers to order industrial products as easily as ordering pizza.

### Core Capabilities

**🔍 Semantic Product Search**  
Instead of browsing through PDF catalogs, customers can ask "I need something to fasten wood to concrete" and get relevant product suggestions. The bot uses OpenAI embeddings stored in Qdrant to understand intent behind vague descriptions.

**🛒 Natural Language Cart Management**  
Customers can say "add 5 of the second item" or "remove the titanium screws" and the bot understands exactly what they mean. No clicking through complex interfaces.

**🧠 Contextual Understanding**  
The bot remembers recent searches and can resolve phrases like "tell me more about the third one" by referencing previous results. This creates a natural conversation flow.

**🏷️ Customer Recognition**  
Returning customers get personalized service with autofilled checkout forms and order history access.

**📄 End-to-End Automation**  
From product search to PDF invoice generation and email delivery – the entire process happens without human intervention.

## Technical Architecture: Modern Python Meets AI

### Backend Stack
The system is built on **FastAPI** with full async support, providing high performance and scalability:

- **🐍 FastAPI + SQLAlchemy 2.0**: Async database operations with PostgreSQL
- **⚡ Redis**: Session management and caching layer
- **🔍 Qdrant**: Vector database for semantic product search
- **🤖 OpenAI GPT-4**: Natural language understanding and intent detection
- **🐳 Docker**: Containerized deployment with Docker Compose

### AI Pipeline Architecture
Every user message goes through a sophisticated NLP pipeline:

1. **Intent Detection**: GPT-4 classifies user intent (search, cart action, question, etc.)
2. **Entity Extraction**: Identifies products, quantities, and customer preferences
3. **Context Resolution**: Resolves references like "the second one" against recent search results
4. **Response Generation**: Crafts appropriate responses and executes actions

### Data Layer Design
The system manages three key data stores:

- **PostgreSQL**: Customer data, orders, and product catalog
- **Redis JSON**: Per-conversation context and shopping carts
- **Qdrant**: 384-dimensional embeddings for 200+ industrial products

## Development Challenges and Solutions

### Challenge 1: Understanding "The 4th Product"
When customers say "tell me about the 4th one," the bot needs to know which search results they're referencing. 

**Solution**: I implemented a custom batch insert function that preserves the exact order of search results in Redis, ensuring consistent product numbering across conversation turns.

### Challenge 2: Async Background Jobs
PDF generation and email sending must happen asynchronously without blocking the chat interface, but SQLAlchemy sessions can't be shared across async contexts.

**Solution**: Background tasks spawn fresh database connections rather than reusing FastAPI's request-scoped sessions.

### Challenge 3: Prompt Engineering for Reliability
Getting consistent intent detection from GPT-4 required significant prompt optimization.

**Solution**: Added confidence thresholds ("If you are not 80% confident, ask for clarification") and few-shot examples that dramatically improved accuracy.

## Real-World Performance

The bot handles several key scenarios flawlessly:

**New Customer Journey**: From "I need wood screws" to completed order in under 60 seconds
**Returning Customer**: Instant reorders based on purchase history
**Complex Queries**: Technical specifications and compatibility questions
**Cart Management**: Natural language modifications ("change the quantity to 10")

## DevOps and Quality Assurance

The project follows modern Python best practices:

- **🔧 GitHub Actions**: Automated CI/CD with Ruff, Black, MyPy, and PyTest
- **🪝 Pre-commit Hooks**: Code quality enforcement
- **📊 Docker Compose**: Local development environment
- **🚀 Production Ready**: Cloud-native architecture for any deployment

## What's Next: The Future of Conversational Commerce

The success of Macroferro points to a larger shift in B2B commerce. Current roadmap includes:

- **💳 Payment Integration**: Stripe and traditional B2B payment terms
- **📊 Admin Dashboard**: React-based interface for inventory and order management  
- **🌍 Multilingual Support**: Spanish and English for broader market reach
- **🔄 ERP Integration**: Real-time inventory sync with existing business systems

## Lessons Learned

Building a production-ready AI assistant taught me several valuable lessons:

1. **Context is King**: The difference between a demo and a product is handling edge cases like "the third option"
2. **Async is Essential**: B2B applications need responsive interfaces even when processing complex backend operations
3. **Prompt Engineering Matters**: Small changes in AI prompts can dramatically impact reliability
4. **User Experience Trumps Technology**: The best tech stack is worthless if the conversation flow feels unnatural

## Try It Yourself

Curious to see conversational commerce in action? 

- **🤖 Live Demo**: Message `@MacroferroBot` on Telegram
- **💻 Source Code**: [github.com/dasafo/macroferro](https://github.com/dasafo/macroferro)
- **📖 Documentation**: Complete interaction examples and setup guides

*What's your experience with AI in B2B applications? Are you seeing similar transformations in your industry? I'd love to hear your thoughts in the comments.*

---

*David Sanchez is a software engineer specializing in AI-powered business applications. Connect with him on [LinkedIn](https://www.linkedin.com/in/dasafodata/) to discuss conversational commerce and modern Python development.*

#ai #chatbot #b2b #ecommerce #fastapi #openai #python #qdrant #telegram
