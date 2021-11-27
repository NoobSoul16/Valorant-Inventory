import traceback, re

from ..file_utilities.filepath import Filepath
from ..entitlements.entitlement_manager import Entitlement_Manager
from .file_manager import File_Manager

class Skin_Loader:

    client = None
    DEBUG_OVERRIDE_OWNED_SKINS = True

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
                new = re.findall('[A-Z][^A-Z]*', n)
                new = " ".join(i for i in new)
            else:
                new = n
        return new


    @staticmethod
    def fetch_content_tier(uuid):

        # define skin tier indices for sorting skins
        content_tiers = Skin_Loader.client.content_tiers

        tier_indices = {
            "Standard": 0,
            "Battlepass": 1,
            "Select": 2,
            "Deluxe": 3,
            "Premium": 4,
            "Exclusive": 5,
            "Ultra": 6,
        }

        if uuid not in ('standard', 'bp'):
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
    def update_skin_database():
        valclient = Skin_Loader.client.client
        client = Skin_Loader.client

        old_data = None

        try:
            old_data = File_Manager.fetch_individual_inventory(valclient)["skins"]
        except KeyError:
            File_Manager.add_region(valclient)
        except Exception as e:
            print(traceback.print_exc())
            print("making fresh skin database")
            Skin_Loader.generate_blank_skin_database()

        skin_level_entitlements = Entitlement_Manager.fetch_entitlements(valclient,"skin_level")["Entitlements"]
        skin_level_entitlements = [item["ItemID"] for item in skin_level_entitlements]

        chroma_level_entitlements = Entitlement_Manager.fetch_entitlements(valclient,"skin_chroma")["Entitlements"]
        chroma_level_entitlements = [item["ItemID"] for item in chroma_level_entitlements]

        inventory = {}

        # iterate through each skin
        for weapon in client.all_weapon_data:
            weapon_payload = {}

            weapon_payload["display_name"] = weapon["displayName"]
            weapon_payload["uuid"] = weapon["uuid"]
            weapon_payload["weapon_type"] = weapon["category"].replace("EEquippableCategory::","") 
            weapon_payload["skins"] = {}

            for skin in weapon["skins"]:
                skin_owned = False
                skin_is_standard = False
                levels = [level["uuid"] for level in skin["levels"]]

                existing_skin_data = None

                if old_data is not None:
                    try:
                        existing_skin_data = old_data[weapon["uuid"]].get("skins").get(skin["uuid"])
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

                if Skin_Loader.DEBUG_OVERRIDE_OWNED_SKINS:
                    skin_owned = True

                if skin_owned:
                    # skin is owned, generate data for it
                    skin_payload = {}
                    
                    skin_payload["display_name"] = skin["displayName"]
                    skin_payload["uuid"] = skin["uuid"]

                    # persistent data
                    skin_payload["favorite"] = existing_skin_data["favorite"] if existing_skin_data is not None else False
                    skin_payload["weight"] = existing_skin_data["weight"] if existing_skin_data is not None else 1


                    tier = ""
                    if skin["contentTierUuid"] is not None:
                        tier = skin["contentTierUuid"]
                    elif skin_is_standard:
                        tier = "standard"
                    else:
                        tier = "bp"
                    skin_payload["content_tier"] = Skin_Loader.fetch_content_tier(tier)


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
                        level_payload["level_type"] = Skin_Loader.sanitize_level_type(level["levelItem"])
                        level_payload["display_icon"] = level["displayIcon"]
                        level_payload["video_preview"] = level["streamedVideo"]

                        level_payload["unlocked"] = level["uuid"] in skin_level_entitlements
                        if skin_is_standard or Skin_Loader.DEBUG_OVERRIDE_OWNED_SKINS:
                            level_payload["unlocked"] = True

                        level_payload["favorite"] = existing_skin_data["levels"][level["uuid"]]["favorite"] if existing_skin_data is not None else False

                    # generate chroma data
                    skin_payload["chromas"] = {}
                    for index, chroma in enumerate(skin["chromas"]):
                        if index == 0:
                            skin_payload["display_icon"] = chroma["fullRender"]

                        skin_payload["chromas"][chroma["uuid"]] = {}
                        chroma_payload = skin_payload["chromas"][chroma["uuid"]]

                        chroma_payload["uuid"] = chroma["uuid"]
                        chroma_payload["index"] = index+1
                        chroma_payload["display_name"] = Skin_Loader.sanitize_chroma_name(chroma["displayName"],skin["displayName"])
                        chroma_payload["display_icon"] = chroma["fullRender"]
                        chroma_payload["swatch_icon"] = chroma["swatch"] 
                        chroma_payload["video_preview"] = chroma["streamedVideo"]        

                        chroma_payload["unlocked"] = chroma["uuid"] in chroma_level_entitlements or index == 0
                        if skin_is_standard or Skin_Loader.DEBUG_OVERRIDE_OWNED_SKINS:
                            chroma_payload["unlocked"] = True

                        chroma_payload["favorite"] = chroma_payload["favorite"] = existing_skin_data["chromas"][chroma["uuid"]]["favorite"] if existing_skin_data is not None else False
                    
                    weapon_payload["skins"][skin["uuid"]] = skin_payload
                    #print(skin_payload)

            inventory[weapon["uuid"]] = weapon_payload

        for weapon,data in inventory.items():
            sort = sorted(data["skins"].items(), key=lambda x: x[1]["content_tier"]["index"], reverse=True)
            inventory[weapon]["skins"] = {i[0]: i[1] for i in sort}

        File_Manager.update_individual_inventory(valclient,inventory,"skins")
        return True

    @staticmethod 
    def fetch_inventory():
        return File_Manager.fetch_individual_inventory(Skin_Loader.client.client)

    @staticmethod
    def generate_blank_skin_database():
        if Skin_Loader.client is not None:
            valclient = Skin_Loader.client.client
            client = Skin_Loader.client
            puuid = valclient.puuid
            region = valclient.region
            weapon_data = client.all_weapon_data


            payload = {
                    weapon["uuid"]: {} for weapon in weapon_data
            }
            File_Manager.update_individual_inventory(valclient, payload, "skins")