import traceback, re, json, logging

from ..file_utilities.filepath import Filepath
from ..entitlements.entitlement_manager import Entitlement_Manager
from .file_manager import File_Manager
from ..client_config import COLLECTIONS_WITH_BAD_LEVEL_IMAGES, UNLOCK_ALL_SKINS, FORCE_DEFAULT_SKINS

from .. import shared

logger_errors = logging.getLogger('VIM_errors')
logger = logging.getLogger('VIM_main')
logger_inv = logging.getLogger('VIM_inventory')

class Skin_Manager:

    @staticmethod 
    def fetch_inventory():
        return File_Manager.fetch_individual_inventory()

    @staticmethod
    def generate_blank_skin_database():
        if shared is not None:
            client = shared.client
            weapon_data = client.all_weapon_data

            payload = {
                weapon["uuid"]: {} for weapon in weapon_data
            }
            File_Manager.update_individual_inventory(payload, "skins")

    @staticmethod
    def sanitize_chroma_name(chroma_name, skin_name):
        try:
            new = chroma_name
            new = new.strip()
            new = new[new.find("(") + 1:new.find(")")]
            if new in skin_name or "Standard" in chroma_name:
                new = "Base"
            return new
        except:
            return "Base"

    @staticmethod
    def sanitize_level_type(type_string):
        new = "Base"
        if type_string is not None:
            n = type_string.replace("EEquippableSkinLevelItem::","")
            if n != "VFX": 
                new = re.findall("[A-Z][^A-Z]*", n)
                new = " ".join(i for i in new)
            else:
                new = n
        return new


    @staticmethod
    def fetch_content_tier(uuid):

        # define skin tier indices for sorting skins
        content_tiers = shared.client.content_tiers

        tier_indices = {
            "Standard": 0,
            "Battlepass": 1,
            "Select": 2,
            "Deluxe": 3,
            "Premium": 4,
            "Exclusive": 5,
            "Ultra": 6,
        }

        if uuid not in ("standard", "bp"):
            for tier in content_tiers:
                if tier["uuid"] == uuid:
                    return { 
                        "dev_name": tier["devName"],
                        "index": tier_indices[tier["devName"]],
                        "display_icon": tier["displayIcon"],
                    }
        elif uuid == "standard":
            return {
                "dev_name": "Standard",
                "display_icon": "https://opengameart.org/sites/default/files/transparent-256x256.png", #PLACEHOLDER
                "index": tier_indices["Standard"]
            }
        elif uuid == "bp":
            return {
                "dev_name": "Battlepass",
                "display_icon": "https://media.valorant-api.com/contenttiers/12683d76-48d7-84a3-4e09-6985794f0445/displayicon.png", #PLACEHOLDER
                "index": tier_indices["Battlepass"]
            }

    @staticmethod 
    def refresh_skin_inventory():
        valclient = shared.client.client
        client = shared.client

        old_data = None

        try:
            old_data = File_Manager.fetch_individual_inventory()["skins"]
        except KeyError:
            old_data = None
        except Exception as e:
            logger_errors.error(traceback.format_exc())
            logger.debug("making fresh skin database")
            Skin_Manager.generate_blank_skin_database()

        skin_level_entitlements = Entitlement_Manager.fetch_entitlements(valclient,"skin_level")["Entitlements"]
        skin_level_entitlements = [item["ItemID"] for item in skin_level_entitlements]

        chroma_level_entitlements = Entitlement_Manager.fetch_entitlements(valclient,"skin_chroma")["Entitlements"]
        chroma_level_entitlements = [item["ItemID"] for item in chroma_level_entitlements]

        inventory = {}

        # iterate through each skin
        for weapon in client.all_weapon_data:
            weapon_payload = {}
            old_weapon_data = {}

            if old_data is not None:
                try:
                    old_weapon_data = old_data[weapon["uuid"]]
                except:
                    pass

            weapon_payload["display_name"] = weapon["displayName"]
            weapon_payload["uuid"] = weapon["uuid"]
            weapon_payload["weapon_type"] = weapon["category"].replace("EEquippableCategory::","") 
            weapon_payload["locked"] = old_weapon_data["locked"] if old_weapon_data.get("locked") and old_weapon_data != {} else False
            weapon_payload["total_weights"] = 0
            weapon_payload["skins"] = {}

            for skin in weapon["skins"]:
                skin_owned = False
                skin_is_standard = False
                levels = [level["uuid"] for level in skin["levels"]]

                existing_skin_data = None

                if old_weapon_data is not None:
                    try:
                        existing_skin_data = old_weapon_data.get("skins").get(skin["uuid"])
                    except:
                        pass

                # check if the currnet iterated skin is owned
                if "Standard" in skin["displayName"] or skin["displayName"] == "Melee": #thanks rito for inconsistent naming schemes
                    skin_owned = True
                    if skin["displayName"] == "Melee":
                        skin["displayName"] = "Standard Melee"
                    skin_is_standard = True
                if not skin_owned:
                    for level in levels:
                        if level in skin_level_entitlements:
                            skin_owned = True
                            break

                if UNLOCK_ALL_SKINS:
                    skin_owned = True

                if FORCE_DEFAULT_SKINS and not skin_is_standard:
                    skin_owned = False

                skin_payload = {}
                
                skin_payload["unlocked"] = skin_owned
                skin_payload["display_name"] = skin["displayName"]
                skin_payload["uuid"] = skin["uuid"]

                # persistent data
                skin_payload["favorite"] = existing_skin_data["favorite"] if existing_skin_data is not None else False
                skin_payload["weight"] = existing_skin_data["weight"] if existing_skin_data is not None else 1
                weapon_payload["total_weights"] += skin_payload["weight"] if skin_payload["favorite"] else 0

                tier = ""
                if skin["contentTierUuid"] is not None:
                    tier = skin["contentTierUuid"]
                elif skin_is_standard:
                    tier = "standard"
                else:
                    tier = "bp"
                skin_payload["content_tier"] = Skin_Manager.fetch_content_tier(tier)
                skin_payload["wallpaper"] = skin["wallpaper"]


                # generate level data
                skin_payload["levels"] = {}
                for index, level in enumerate(skin["levels"]):
                    skin_payload["levels"][level["uuid"]] = {}
                    level_payload = skin_payload["levels"][level["uuid"]]

                    level_payload["uuid"] = level["uuid"]

                    level_payload["display_name"] = level["displayName"]
                    if level["displayName"] is None:
                        level_payload["displayName"] = f"{skin['displayName']} Level {index + 1}"
                    
                    level_payload["shorthand_display_name"] = f"LVL{index+1}"
                    
                    level_payload["index"] = index + 1
                    level_payload["level_type"] = Skin_Manager.sanitize_level_type(level["levelItem"])
                    level_payload["display_icon"] = level["displayIcon"]
                    level_payload["video_preview"] = level["streamedVideo"]

                    level_payload["unlocked"] = level["uuid"] in skin_level_entitlements
                    if skin_is_standard or UNLOCK_ALL_SKINS:
                        level_payload["unlocked"] = True

                    if skin["themeUuid"] in COLLECTIONS_WITH_BAD_LEVEL_IMAGES:
                        level_payload["display_icon"] = skin["chromas"][0]["displayIcon"]

                    level_payload["favorite"] = existing_skin_data["levels"][level["uuid"]]["favorite"] if existing_skin_data is not None else False
                
                # favorite level if there is only one
                if len(skin_payload["levels"]) == 1:
                    for _,level in skin_payload["levels"].items():
                        if level["unlocked"]:
                            level["favorite"] = True

                # generate chroma data
                skin_payload["chromas"] = {}
                for index, chroma in enumerate(skin["chromas"]):
                    if index == 0:
                        skin_payload["display_icon"] = chroma["fullRender"]

                    skin_payload["chromas"][chroma["uuid"]] = {}
                    chroma_payload = skin_payload["chromas"][chroma["uuid"]]

                    chroma_payload["uuid"] = chroma["uuid"]
                    chroma_payload["index"] = index+1
                    chroma_payload["display_name"] = Skin_Manager.sanitize_chroma_name(chroma["displayName"],skin["displayName"])
                    chroma_payload["display_icon"] = chroma["fullRender"]
                    chroma_payload["swatch_icon"] = chroma["swatch"] 
                    chroma_payload["video_preview"] = chroma["streamedVideo"]        

                    chroma_payload["unlocked"] = chroma["uuid"] in chroma_level_entitlements or index == 0
                    if skin_is_standard or UNLOCK_ALL_SKINS:
                        chroma_payload["unlocked"] = True

                    chroma_payload["favorite"] = existing_skin_data["chromas"][chroma["uuid"]]["favorite"] if existing_skin_data is not None else False
                
                # favorite chroma if there is only one
                if len(skin_payload["chromas"]) == 1:
                    for _,chroma in skin_payload["chromas"].items():
                        if chroma["unlocked"]:
                            chroma["favorite"] = True

                weapon_payload["skins"][skin["uuid"]] = skin_payload

            inventory[weapon["uuid"]] = weapon_payload

        for weapon,data in inventory.items():
            unlocked_skins = {uuid: skin for uuid,skin in data["skins"].items() if skin["unlocked"]}
            locked_skins = {uuid: skin for uuid,skin in data["skins"].items() if not skin["unlocked"]}

            sort_unlocked = sorted(unlocked_skins.items(), key=lambda x: x[1]["content_tier"]["index"], reverse=True)
            sort_locked = sorted(locked_skins.items(), key=lambda x: x[1]["content_tier"]["index"], reverse=True)

            inventory[weapon]["skins"] = {i[0]: i[1] for i in sort_unlocked}
            inventory[weapon]["skins"].update({i[0]: i[1] for i in sort_locked})

        #logger_inv.debug(f"skin inventory:\n{json.dumps(inventory)}")
        File_Manager.update_individual_inventory(inventory,"skins")
        return True


    @staticmethod
    async def update_inventory(**kwargs):
        payload = json.loads(kwargs.get("payload"))
        inventory_data = payload.get("inventoryData")
        skins_data = payload.get("skinsData")
        weapon_uuid = payload.get("weaponUuid")

        inventory = Skin_Manager.fetch_inventory()["skins"]

        weapon_data = inventory[weapon_uuid]
        weapon_data["locked"] = inventory_data["locked"]
        weapon_data["total_weights"] = 0

        # update favorites and ensure valid favorites combos
        for skin_uuid, skin_data in weapon_data["skins"].items():

            # update skin weight
            skin_data["weight"] = skins_data[skin_uuid]["weight"]
            weapon_data["total_weights"] += skin_data["weight"] if skin_data["favorite"] else 0

            def find_top_unlocked(key):
                for index in range(len(skin_data[key])-1,-1,-1):
                    data = skin_data[key][list(skin_data[key].keys())[index]]
                    if data["unlocked"]:
                        return data

            # update favorites
            skin_data["favorite"] = skins_data[skin_uuid]["favorite"]
            for level_uuid, level_data in skin_data["levels"].items():
                level_data["favorite"] = skins_data[skin_uuid]["levels"][level_uuid]["favorite"]
            for chroma_uuid, chroma_data in skin_data["chromas"].items():
                chroma_data["favorite"] = skins_data[skin_uuid]["chromas"][chroma_uuid]["favorite"]

            if skin_data["favorite"]:
                # make sure theres at least one enabled level/chroma if the skin is favorited
                level_count = len(skin_data["levels"].keys())
                chroma_count = len(skin_data["chromas"].keys())

                favorited_levels = [level for _, level in skin_data["levels"].items() if level["favorite"]]
                favorited_chromas = [chroma for _, chroma in skin_data["chromas"].items() if chroma["favorite"]]

                # if a lower level is favorited, make sure the lowest chroma is also favorited
                for level in favorited_levels:
                    level_data = skin_data["levels"][level["uuid"]]
                    if level_data["index"] < level_count:
                        chroma = skin_data["chromas"][list(skin_data["chromas"].keys())[0]]
                        chroma["favorite"] = True
                        favorited_chromas.append(chroma)
                        

                # if a high level chroma is favorited and max level is not, favorite the max level
                for chroma in favorited_chromas:
                    chroma_data = skin_data["chromas"][chroma["uuid"]]
                    if chroma_data["index"] != 1:
                        level = find_top_unlocked("levels")
                        level["favorite"] = True
                        favorited_levels.append(level)

                if len(favorited_levels) == 0:
                    find_top_unlocked("levels")["favorite"] = True

                if len(favorited_chromas) == 0:
                    find_top_unlocked("chromas")["favorite"] = True

        File_Manager.update_individual_inventory(inventory,"skins")
        await shared.client.broadcast_loadout()

        return inventory