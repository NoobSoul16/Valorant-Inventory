import psutil, os, json, asyncio

from .. import shared

class System:

    def are_processes_running(required_processes=["VALORANT-Win64-Shipping.exe", "RiotClientServices.exe"]):
        processes = []
        for proc in psutil.process_iter():
            processes.append(proc.name())
        
        return set(required_processes).issubset(processes)

    async def start_game():
        if not System.are_processes_running():
            path = System.get_rcs_path()
            psutil.subprocess.Popen([path, "--launch-product=valorant", "--launch-patchline=live"])
            while not System.are_processes_running():
                await asyncio.sleep(1)
            
            while shared.client.client == None:
                shared.client.check_connection()
                print("waiting for client")
                await asyncio.sleep(1)

            while shared.client.client.fetch_presence() is None:
                print("waiting for presence")
                await asyncio.sleep(1)

            return True
        else:
            return True

    def get_rcs_path():
        riot_installs_path = os.path.expandvars("%PROGRAMDATA%\\Riot Games\\RiotClientInstalls.json")
        try:
            with open(riot_installs_path, "r") as file:
                client_installs = json.load(file)
                rcs_path = os.path.abspath(client_installs["rc_default"])
                if not os.access(rcs_path, os.X_OK):
                    return None
                return rcs_path
        except FileNotFoundError:
            return None