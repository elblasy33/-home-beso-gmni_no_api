import argparse
import uvicorn
import os
from src.config import settings

def main():
    parser = argparse.ArgumentParser(description="Browser AI Automation Agent")
    parser.add_argument("--host", default=settings.APP_HOST, help="Host address to bind")
    parser.add_argument("--port", type=int, default=settings.APP_PORT, help="Port to listen on")
    parser.add_argument("--headed", action="store_true", help="Launch browser in headed mode (visible window)")
    parser.add_argument("--headless", action="store_true", help="Launch browser in headless mode (default)")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload")
    
    args = parser.parse_args()

    if args.headed:
        settings.HEADLESS = False
        os.environ["HEADLESS"] = "false"
    elif args.headless:
        settings.HEADLESS = True
        os.environ["HEADLESS"] = "true"

    print("=" * 65)
    print("🚀 Starting Browser AI Automation Agent")
    print(f"📍 Web UI & API: http://{args.host}:{args.port}")
    print(f"🧪 Local Mock AI Site: http://{args.host}:{args.port}/mock-site/chat")
    print(f"🌐 Browser Mode: {'Headed (Visible)' if not settings.HEADLESS else 'Headless (Background)'}")
    print(f"📁 Persistent Profile: {settings.BROWSER_PROFILE_DIR}")
    print("=" * 65)

    uvicorn.run(
        "src.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()
