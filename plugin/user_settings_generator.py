from .utils import printSuccessMessage, printWarningMessage, get_user_settings_path
import json
import os

class UserSettingsGenerator:

    def __init__(self, dialog):
        self.dialog = dialog
        self.user_settings_path = get_user_settings_path()

    def run(self):
        self.user_settings_dict = {
            "operator": self.dialog.lineOperator.text(),
            
            "output_folder": self.dialog.usersettingsPath.filePath(),
            "userfolder": self.dialog.usersettingsPath.filePath(),

            "background_url": self.dialog.lineBGURL.text(),

            # azure connection string
            "azure_key": self.dialog.lineAzurekey.text(),
        }

        if self.validate_input():
            self.write_user_settings()
            self.dialog.done(1)

    def write_user_settings(self):

        printSuccessMessage(f"Writing settings file: operator {self.user_settings_path}")

        with open(self.user_settings_path, "w", encoding='utf-8') as file:
            json.dump(self.user_settings_dict, file, ensure_ascii=False, indent=4)
        

    def validate_input(self):
        
        # check if all fields has a value
        if not all([val != "" for val in self.user_settings_dict.values()]):
            printWarningMessage("Alle felt må fylles ut")
            return False
        
        # check if background-url contains correct file
        if not "background.gpkg" in self.user_settings_dict["background_url"]: 
            printWarningMessage("Feil verdi for URL bakgrunnskart")
            return False
        
        # check if operator-name contains a space
        if not " " in self.user_settings_dict["operator"]:
            printWarningMessage("Operatørnavn ikke godkjent. Husk å skrive både navn og etternavn (på formen Navn Etternavn)")
            return False
        
        # check if folder-path exists
        if not os.path.exists(self.user_settings_dict["userfolder"]) and not os.path.exists(self.user_settings_dict["output_folder"]):
            printWarningMessage("Ugyldig mappeplassering. Velg en eksisternde mappe")
            return False        
        
        return True