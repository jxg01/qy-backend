from channels.generic.websocket import AsyncJsonWebsocketConsumer

class RunConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.run_id = self.scope["url_route"]["kwargs"]["run_id"]
        self.group = f"run_{self.run_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def run_event(self, event):
        await self.send_json(event["data"])
