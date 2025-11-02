# 🔥🌍 WorldOnFire

> **Where is the world heating up right now?**

Every minute, every second, every millisecond — something happens somewhere on the planet. The world is constantly on fire with events. Some are minor, but major ones shape history. **WorldOnFire** is a comprehensive real-time news heatmap that shows where the news is truly popping off, revealing the heartbeat of our planet in real time.

![WorldOnFire Banner](https://github.com/user-attachments/assets/cc17c849-802c-46fb-ac30-5e7247819962)

## Overview

WorldOnFire aggregates and visualises breaking news from 100+ major cities worldwide, creating an interactive heatmap that updates every 10 minutes. Watch as global events unfold in real-time, with intensity indicators showing where the most significant events are happening.

### Key Features

- **Real-Time Global Heatmap** - Visual representation of news intensity across 100+ major cities
- **Live Updates** - Fresh news data every 10 minutes from Event Registry API
- **Location-Based Analysis** - Automatic extraction and categorisation of news by city
- **Historical Tracking** - Archive of news events for trend analysis
- **City-Specific Views** - Deep dive into news from any tracked location
- **Heat Intensity** - Color-coded visualisation showing news activity levels

## Tech Stack

### Backend
- **FastAPI** - High-performance Python web framework
- **Supabase** - PostgreSQL database for news storage
- **Event Registry API** - Real-time news data source
- **Python 3.9+** - Core language

### Frontend
- **Next.js** - React framework for production
- **Tailwind CSS** - Styling
- **Mapping Library** - Leaflet/Mapbox for heatmap visualisation

### APIs & Services
- **Event Registry** - News aggregation API
- **Supabase** - Database and authentication
- **RESTful API** - Custom backend endpoints

## Architecture
```
┌─────────────────┐
│  Event Registry │
│      API        │
└────────┬────────┘
         │ Every 10 minutes
         ▼
┌─────────────────┐
│   FastAPI       │
│   Backend       │◄────────┐
│  • Parse News   │         │
│  • Extract City │         │
│  • Calculate    │         │
│    Heat Score   │         │
└────────┬────────┘         │
         │                  │
         ▼                  │
┌─────────────────┐         │
│   Supabase      │         │
│   PostgreSQL    │         │
│  • Store News   │         │
│  • Track Cities │         │
└────────┬────────┘         │
         │                  │
         │                  │
         ▼                  │
┌─────────────────┐         │
│    Next.js      │         │
│    Frontend     │─────────┘
│  • Heatmap View │  API Requests
│  • City Details │
│  • Analytics    │
└─────────────────┘
```

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- Supabase account
- Event Registry API key

### Backend Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/worldonfire.git
cd worldonfire/backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file in the backend directory:
```env
EVENT_REGISTRY_API_KEY=your_event_registry_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

5. **Set up Supabase database**
Run the SQL schema:
```sql
CREATE TABLE news (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    location TEXT NOT NULL,
    image_url TEXT,
    description TEXT,
    published_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_url TEXT,
    heat_score INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_news_location ON news(location);
CREATE INDEX idx_news_published_at ON news(published_at DESC);
```

6. **Run the backend**
```bash
uvicorn main:app --reload --port 8000
```

### Frontend Setup

1. **Navigate to frontend directory**
```bash
cd ../frontend
```

2. **Install dependencies**
```bash
npm install
```

3. **Configure environment variables**
Create a `.env.local` file:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

4. **Run the development server**
```bash
npm run dev
```

5. **Open your browser**
Navigate to `http://localhost:3000`

## API Endpoints

### Backend API

#### **POST** `/api/news/fetch`
Fetch and store latest news from Event Registry API
```bash
curl -X POST http://localhost:8000/api/news/fetch
```

#### **GET** `/api/news`
Retrieve all news from database
```bash
curl http://localhost:8000/api/news
```

#### **GET** `/api/news/city/{city_name}`
Get news by specific city
```bash
curl http://localhost:8000/api/news/city/London
```

#### **GET** `/api/news/heatmap`
Get aggregated news data for heatmap visualisation
```bash
curl http://localhost:8000/api/news/heatmap
```

#### **GET** `/api/cities`
Get list of all tracked cities
```bash
curl http://localhost:8000/api/cities
```

## How it works

1. **Data Collection**: Every 10 minutes, the backend queries Event Registry API for news from 100+ major cities worldwide

2. **Processing**: Each article is analyzed to extract:
   - Title
   - Description
   - Location (city)
   - Images
   - Publication date
   - Source URL

3. **Storage**: Processed news articles are stored in Supabase PostgreSQL database

4. **Heat Calculation**: Algorithm calculates "heat score" based on:
   - Number of articles from a location
   - Recency of articles
   - Article importance (based on source ranking)

5. **Visualisation**: Frontend fetches aggregated data and renders an interactive heatmap showing news intensity by location

6. **Real-time Updates**: Frontend polls for updates every 10 minutes to keep the heatmap current


<p align="center">Made with 🔥 by Team Tourists</p>
<p align="center">
  <a href="#top">⬆️ Back to Top</a>
</p>

