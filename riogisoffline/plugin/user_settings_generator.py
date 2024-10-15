import riogisoffline.plugin.utils as utils
import json
import os

class UserSettingsGenerator:

    def __init__(self, dialog):
        self.dialog = dialog
        self.user_settings_path = utils.get_user_settings_path()

    def run(self):
        
        self.user_settings_dict = {
            "operator": self.dialog.lineOperator.text(),
            "background_url": self.dialog.lineBGURL.text(),

            # azure connection string
            "azure_key": self.dialog.lineAzurekey.text(),
        }

        project_dir_name = "RioGIS offline"
        self.user_input_folder_path = self.dialog.usersettingsPath.filePath()

        # select project folder if user selectes project-folder instead of parent
        if project_dir_name in os.path.split(self.user_input_folder_path)[-1]:
            self.user_settings_dict["userfolder"] = self.user_input_folder_path
        else:
            self.user_settings_dict["userfolder"] = os.path.join(self.user_input_folder_path, project_dir_name)
        
        self.user_settings_dict["output_folder"] = os.path.join(self.user_settings_dict["userfolder"], "output")
        self.user_settings_dict["file_folder"] = os.path.join(self.user_settings_dict["userfolder"], "filer")

        if self.validate_input():
            self.write_user_settings()
            self.dialog.done(1)

    def write_user_settings(self):

        utils.printSuccessMessage(f"Writing settings file: operator {self.user_settings_path}")

        with open(self.user_settings_path, "w", encoding='utf-8') as file:
            json.dump(self.user_settings_dict, file, ensure_ascii=False, indent=4)

        file_folder = self.user_settings_dict["file_folder"]
        backup = os.path.join(file_folder, 'bruker_settings_BACKUP.json')

        if not os.path.exists(file_folder):
            os.makedirs(file_folder, exist_ok=True)

        with open(backup, "w", encoding='utf-8') as file:
            json.dump(self.user_settings_dict, file, ensure_ascii=False, indent=4)
        

    def validate_input(self):
        
        # check if all fields has a value
        if not all([val != "" for val in self.user_settings_dict.values()]):
            utils.printWarningMessage("Alle felt må fylles ut")
            return False
        
        # check if background-url contains correct file
        if not "background.gpkg" in self.user_settings_dict["background_url"]: 
            utils.printWarningMessage("Feil verdi for URL bakgrunnskart")
            return False
        
        # check if operator-name contains a space
        if not " " in self.user_settings_dict["operator"]:
            utils.printWarningMessage("Operatørnavn ikke godkjent. Husk å skrive både navn og etternavn (på formen Navn Etternavn)")
            return False
        
        # check if folder-path exists
        if not os.path.exists(self.user_input_folder_path):
            utils.printWarningMessage("Ugyldig mappeplassering. Velg en eksisternde mappe")
            return False        
        
        return True