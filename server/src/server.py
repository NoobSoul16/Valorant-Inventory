import asyncio
import websockets, json, traceback, os, ssl, pathlib
import websockets.client 
import websockets.server
from websockets.exceptions import ConnectionClosedOK 

from .client_management.client import Client
from .inventory_management.skin_loader import Skin_Loader
from .randomizers.skin_randomizer import Skin_Randomizer
from .file_utilities.filepath import Filepath
from .client_config import DEBUG_PRINT

# ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
# path_cert = pathlib.Path(__file__).with_name("cert.pem")
# path_key = pathlib.Path(__file__).with_name("key.pem")
# ssl_context.load_cert_chain(path_cert, keyfile=path_key)

class Server:

    client = Client()

    # send client object to submodules
    Skin_Loader.client = client
    Skin_Randomizer.client = client

    sockets = []

    request_lookups = {
        "handshake": lambda: True,
        "fetch_loadout": client.fetch_loadout,
        "refresh_inventory": Skin_Loader.update_skin_database,
        "randomize_skins": Skin_Randomizer.randomize,
        "fetch_inventory": Skin_Loader.fetch_inventory,
        "put_weapon": client.put_weapon,
        "update_inventory": Skin_Loader.update_inventory
    }

    @staticmethod
    def start():
        if not os.path.exists(Filepath.get_appdata_folder()):
            os.mkdir(Filepath.get_appdata_folder())

        start_server = websockets.serve(Server.ws_entrypoint, "", 8765)

        print("refreshing inventory")
        Server.request_lookups["refresh_inventory"]()
        
        print("server running\nopen https://colinhartigan.github.io/valorant-skin-manager in your browser to use")
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()


    @staticmethod
    async def ws_entrypoint(websocket, path):
        DEBUG_PRINT("connected")
        DEBUG_PRINT(Server.sockets)
        Server.sockets.append(websocket)
        try:
            while websocket in Server.sockets:
                data = await websocket.recv()
                data = json.loads(data)

                request = data.get("request")
                args = data.get("args")
                has_kwargs = True if args is not None else False
                DEBUG_PRINT("got a request")
                DEBUG_PRINT(f"request: {request}")
                payload = {}

                if request in Server.request_lookups.keys():
                    payload = {
                        "success": True,
                        "request": request,
                        "response": None,
                    }
                    if has_kwargs:
                        payload["response"] = Server.request_lookups[request](**args)
                    else:
                        payload["response"] = Server.request_lookups[request]()
                else:
                    payload = {
                        "success": False,
                        "response": "could not find the specified request"
                    }

                await websocket.send(json.dumps(payload))
                DEBUG_PRINT("responded w/ payload\n----------------------")
        
        except ConnectionClosedOK:
            DEBUG_PRINT("disconnected")
            Server.sockets.pop(Server.sockets.index(websocket))
            
        except Exception:
            print("----- EXCEPTION -----")
            print(traceback.print_exc())