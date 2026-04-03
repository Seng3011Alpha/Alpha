# TEAM H18A - ALPHA

## Overview

The Market Event Intelligence Service is a microservice that collects financial news and stock market data, processes and standardises event datasets, performs sentiment and analytical modelling, and provides APIs for retrieving event intelligence data.
The service integrates into the Event Intelligence Ecosystem and is designed to be interoperable with other teams microservices.

## Table of Contents

- [Microservices](#microservices)
- [API Overview](#api-overview)
- [Running the service](#running-the-service)
- [Testing](#testing)
- [Observability](#observability)
- [Interoperability](#interoperability)
- [Project Structure](#project-structure)
- [Deployment](#deployment)


## Microservices

Our system is built using multiple microservices that work together to collect, process, store, and analyse financial event data.

### Collection Service
The collection service is responsible for retrieving external data from financial news and stock market APIs.  
It collects raw datasets and prepares them for processing.

### Processing Service
The processing service standardises collected datasets into a structured event data format.  
This ensures that datasets follow a consistent schema and can be used for analytics and interoperability.

### Storage Service
The storage service stores both raw and processed datasets.  
It supports saving and loading datasets in JSON format and ensures data persistence across services.

### Analytics Service
The analytics service performs sentiment analysis and price analytics on collected financial datasets.  
It generates analytical outputs that can be retrieved through the API.

### API Service
The API service exposes endpoints for data collection, dataset retrieval, analytics, and service interaction.  
It allows other teams and applications to interact with our microservices through HTTP endpoints.


## API Overview

Our service exposes REST API endpoints for data collection, storage, analytics, and dataset retrieval.

### Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /collect/stocks | Collect stock market data |
| POST | /collect/news | Collect financial news data |
| POST | /collect/history | Collect historical stock data |
| POST | /collect/pipeline | Run full data collection pipeline |
| GET | /api/news | Retrieve news data |
| GET | /api/stock | Retrieve stock data |
| GET | /api/analysis | Retrieve analytics results |
| GET | /api/sentiment | Retrieve sentiment analysis |
| GET | /api/events | Retrieve event datasets |


## Running the Service

### Run with Docker
```bash
docker-compose up --build


Run tests using:
```bash
pytest

