# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy


class DSC_OT_object_pedestrian(bpy.types.Operator):
    bl_idname = "dsc.object_pedestrian"
    bl_label = "Pedestrian"
    bl_description = "Place a pedestrian object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return False

    def execute(self, context):
        self.report({'INFO'}, "Not implemented.")

        return {'FINISHED'}