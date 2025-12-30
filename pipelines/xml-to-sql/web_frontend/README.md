# XML to SQL Converter - Frontend

React frontend for the XML to SQL converter web application.

## Development

### Prerequisites

- Node.js 18+ and npm

### Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

The frontend will be available at http://localhost:5173 and will proxy API requests to the backend at http://localhost:8000.

## Building for Production

Build the frontend for production:

```bash
npm run build
```

The built files will be in the `dist/` directory, which will be served by the FastAPI backend.

## Project Structure

- `src/components/` - React components
- `src/services/` - API client functions
- `src/App.jsx` - Main application component
- `src/main.jsx` - Application entry point

