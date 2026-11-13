"""Cliente HTTP mínimo hacia API Gateway en MiniStack y limpieza por claves exactas."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lambdas.shared.config.settings import ROOT, Settings
from lambdas.shared.infrastructure.clients import DynamoDBAdapter
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import serialize


class Api:
    def __init__(self):
        settings = Settings.load()
        outputs = json.loads((ROOT / ".local/outputs.json").read_text())
        # URL construida desde configuración validada, no desde una URL arbitraria del disco.
        self.base = f"{settings.endpoint}/_aws/execute-api/{outputs['ApiId']}/local"
        self.created = {"stores": set(), "couriers": set(), "orders": set(), "requests": set()}

    def call(self, method, path, body=None, token=None, key=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if key:
            headers["Idempotency-Key"] = key
        request = Request(self.base + path, method=method, headers=headers,
                          data=json.dumps(body).encode() if body is not None else None)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else None

    def login(self, user_id, role):
        body = {"userId": user_id, "role": role}
        if role == "ADMIN":
            body["adminCode"] = "admin-local"
        status, session = self.call("POST", "/api/v1/auth/dev-login", body)
        assert status == 200, session
        if role == "STORE":
            self.created["stores"].add(user_id)
        if role == "COURIER":
            self.created["couriers"].add(user_id)
        return session["token"]

    def track(self, actor_id, operation, request_id):
        self.created["requests"].add((actor_id, operation, request_id))

    def cleanup(self):
        adapter = DynamoDBAdapter()
        doomed = [keys.profile(keys.store(s)) for s in self.created["stores"]]
        for c in self.created["couriers"]:
            doomed += [keys.profile(keys.courier(c)), keys.active(c)]
        for order_id in self.created["orders"]:
            order = adapter.get_item(Key=serialize(keys.meta(order_id)), ConsistentRead=True).get("Item")
            doomed.append(keys.meta(order_id))
            if order:
                doomed.append(keys.store_view(order["storeId"]["S"], order_id))
            for c in self.created["couriers"]:
                doomed.append(keys.courier_view(c, order_id))
            events = adapter.query(KeyConditionExpression="PK = :pk AND begins_with(SK, :e)",
                                   ExpressionAttributeValues=serialize({":pk": keys.order(order_id), ":e": "EVENT#"}))
            doomed += [{"PK": e["PK"]["S"], "SK": e["SK"]["S"]} for e in events["Items"]]
        doomed += [keys.request(keys.request_scope(a, op), r) for a, op, r in self.created["requests"]]
        for key in doomed:
            adapter.client.delete_item(TableName=adapter.settings.table_name, Key=serialize(key))
