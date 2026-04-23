import json
import asyncio
import redis.asyncio as redis_async
from app.application.interfaces import IEventStreamService

class RedisEventStreamAdapter(IEventStreamService):
    def __init__(self, redis_url: str):
        self.redis_url = redis_url

    async def subscribe_to_job_events(self, job_id: str):
        # Connection is established using the injected URL
        r = redis_async.from_url(self.redis_url)
        pubsub = r.pubsub()
        channel_name = f"channel:job:{job_id}"
        
        await pubsub.subscribe(channel_name)
        
        try:
            yield {"status": "CONNECTED", "message": "Listening for updates"}
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    # It returns the native dictionary, not formatted text for web
                    yield json.loads(message["data"].decode("utf-8"))
        
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel_name)
            await r.aclose()