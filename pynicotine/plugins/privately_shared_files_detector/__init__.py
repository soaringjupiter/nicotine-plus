# COPYRIGHT (C) 2020-2024 Nicotine+ Contributors
# COPYRIGHT (C) 2011 quinox <quinox@users.sf.net>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pynicotine.pluginsystem import BasePlugin


class Plugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = {
            "threshold_percentage": 50,  # Default threshold percentage
        }
        self.metasettings = {
            "threshold_percentage": {
                "description": "Threshold percentage of private files to ban users",
                "type": "int",
                "minimum": 0,
                "maximum": 100,
            },
        }
        self.probed_users = {}

    def loaded_notification(self):
        self.log(
            "Plugin to ban users who share files privately over a threshold percentage loaded.",
        )

    def check_user(self, user, public_files, private_files):
        if user not in self.probed_users:
            return

        if self.probed_users[user] == "okay":
            return

        total_files = public_files + private_files
        private_percentage = (
            (private_files / total_files) * 100 if total_files > 0 else 0
        )

        if private_percentage > self.settings["threshold_percentage"]:
            self.ban_user(user)
            self.probed_users[user] = "banned"
            self.log(
                f"Banned user {user} who shares {private_percentage:.2f}% of files privately.",
            )
        else:
            self.probed_users[user] = "okay"
            self.log(
                f"User {user} shares {private_percentage:.2f}% of files privately, which is below the threshold.",
            )

    def ban_user(self, user):
        self.core.network_filter.ban_user(user)

    def upload_queued_notification(self, user, virtual_path, real_path):
        if user in self.probed_users:
            return

        self.probed_users[user] = "requesting_stats"
        self.core.userbrowse.request_user_shares(user)

    def user_stats_notification(self, user, stats):
        browsed_user = self.core.userbrowse.users.get(user)
        if browsed_user:
            public_files = sum(
                len(files) for files in browsed_user.public_folders.values()
            )
            private_files = sum(
                len(files) for files in browsed_user.private_folders.values()
            )
            self.check_user(
                user,
                public_files=public_files,
                private_files=private_files,
            )

    def upload_finished_notification(self, user, *_):
        if user not in self.probed_users:
            return

        if self.probed_users[user] != "banned":
            return

        self.log(
            f"Finished processing user {user} who shares files privately over the threshold.",
        )

    def configure(self):
        self.settings["threshold_percentage"] = self.get_setting(
            "threshold_percentage",
            self.settings["threshold_percentage"],
        )

    def get_setting(self, setting_name, default_value):
        setting = self.core.config.sections["plugin"].get(setting_name, default_value)
        return int(setting)
