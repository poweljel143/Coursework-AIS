import pika
import json
import os
from datetime import datetime
from typing import Callable, Dict
import threading

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

class MessageBroker:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.consumers = {}

    def connect(self):
        if not self.connection or self.connection.is_closed:
            self.connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            self.channel = self.connection.channel()

    def publish_event(self, exchange: str, routing_key: str, event_data: dict):
        """Publish event to message broker"""
        try:
            self.connect()
            self.channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)

            event = {
                "event_id": f"{exchange}.{routing_key}.{datetime.utcnow().timestamp()}",
                "event_type": routing_key,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": event_data
            }

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
        except Exception as e:
            print(f"Error publishing event: {e}")

    def subscribe_to_events(self, exchange: str, routing_keys: list, callback: Callable):
        """Subscribe to events from message broker"""
        try:
            self.connect()
            self.channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)

            # Create exclusive queue for this consumer
            result = self.channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue

            # Bind queue to routing keys
            for routing_key in routing_keys:
                self.channel.queue_bind(
                    exchange=exchange,
                    queue=queue_name,
                    routing_key=routing_key
                )

            def wrapper(ch, method, properties, body):
                try:
                    event = json.loads(body)
                    callback(event)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"Error processing event: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            self.channel.basic_consume(queue=queue_name, on_message_callback=wrapper)

            # Start consuming in a separate thread
            consumer_key = f"{exchange}_{queue_name}"
            self.consumers[consumer_key] = threading.Thread(
                target=self.channel.start_consuming,
                daemon=True
            )
            self.consumers[consumer_key].start()

        except Exception as e:
            print(f"Error subscribing to events: {e}")

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()

# Global message broker instance
message_broker = MessageBroker()