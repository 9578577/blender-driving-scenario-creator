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
import bmesh
from mathutils import Vector, Matrix

from math import pi

from . import helpers


class DSC_OT_two_point_base(bpy.types.Operator):
    bl_idname = 'dsc.two_point_base'
    bl_label = 'DSC snap draw operator'
    bl_options = {'REGISTER', 'UNDO'}

    snap_filter = None

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def create_object(self, context):
        '''
            Create a junction object
        '''
        raise NotImplementedError()

    def create_stencil(self, context, point_start, heading_start, snapped_start):
        '''
            Create a stencil object with fake user or find older one in bpy data and
            relink to scene currently only support OBJECT mode.
        '''
        stencil = bpy.data.objects.get('dsc_stencil')
        if stencil is not None:
            if context.scene.objects.get('dsc_stencil') is None:
                context.scene.collection.objects.link(stencil)
        else:
            # Create object from mesh
            mesh = bpy.data.meshes.new("dsc_stencil")
            vertices, edges, faces = self.get_initial_vertices_edges_faces()
            mesh.from_pydata(vertices, edges, faces)
            # Rotate in start heading direction
            self.stencil = bpy.data.objects.new("dsc_stencil", mesh)
            self.stencil.location = point_start
            # Link
            context.scene.collection.objects.link(self.stencil)
            self.stencil.use_fake_user = True
            self.stencil.data.use_fake_user = True
        # Make stencil active object
        helpers.select_activate_object(context, self.stencil)

    def remove_stencil(self):
        '''
            Unlink stencil, needs to be in OBJECT mode.
        '''
        stencil = bpy.data.objects.get('dsc_stencil')
        if stencil is not None:
            bpy.data.objects.remove(stencil, do_unlink=True)

    def update_stencil(self, context):
        '''
            Transform stencil object to follow the mouse pointer.
        '''
        if self.point_selected_end == self.point_start:
            # This can happen due to start point snapping -> ignore
            return
        # Try getting data for a new mesh
        valid, mesh, matrix_world, materials = self.get_mesh_update_params(context, for_stencil=True)
        # If we get a valid solution we can update the mesh, otherwise just return
        if valid:
            helpers.replace_mesh(self.stencil, mesh)
            # Set stencil global transform
            self.stencil.matrix_world = matrix_world

    def get_initial_vertices_edges_faces(self):
        '''
            Calculate and return the vertices, edges and faces to create the initial stencil mesh.
        '''
        vertices = [(0.0, 0.0, 0.0)]
        edges = []
        faces = []
        return vertices, edges, faces

    def get_mesh_update_params(self, context, for_stencil=True):
        '''
            Calculate and return the vertices, edges and faces to create a road mesh.
        '''
        raise NotImplementedError()

    def modal(self, context, event):
        # Display help text
        if self.state == 'INIT':
            context.workspace.status_text_set("Place object by clicking, hold CTRL to snap to grid, "
                "press RIGHTMOUSE to cancel selection, press ESCAPE to exit.")
            # Set custom cursor
            bpy.context.window.cursor_modal_set('CROSSHAIR')
            # Reset snapping
            self.snapped_start = False
            self.state = 'SELECT_START'
        if event.type in {'NONE', 'TIMER', 'TIMER_REPORT', 'EVT_TWEAK_L', 'WINDOW_DEACTIVATE'}:
            return {'PASS_THROUGH'}
        # Update on move
        if event.type == 'MOUSEMOVE':
            # Snap to existing objects if any, otherwise xy plane
            self.hit, self.id_xodr_hit, self.cp_type, point_selected, heading_selected = \
                helpers.raycast_mouse_to_object_else_xy(context, event, filter=self.snap_filter)
            context.scene.cursor.location = point_selected
            # CTRL activates grid snapping if not snapped to object
            if event.ctrl and not self.hit:
                bpy.ops.view3d.snap_cursor_to_grid()
                point_selected = context.scene.cursor.location
            # Process and remember points according to modal state machine
            if self.state == 'SELECT_START':
                self.point_start = point_selected.copy()
                self.heading_start = heading_selected
                # Make sure end point and heading are set even if mouse is not moved
                self.point_selected_end = point_selected
                self.heading_end = heading_selected
            if self.state == 'SELECT_END':
                # For snapped case use projected end point
                self.point_selected_end = point_selected
                self.snapped_end = self.hit
                if self.snapped_end:
                    self.heading_end = heading_selected + pi
                else:
                    self.heading_end = self.calculate_heading_end(self.point_start,
                        self.heading_start, self.point_selected_end)
                self.update_stencil(context)
                context.scene.cursor.location = point_selected
        # Select start and end
        elif event.type == 'LEFTMOUSE':
            if event.value == 'RELEASE':
                if self.state == 'SELECT_START':
                    self.snapped_start = self.hit
                    self.id_xodr_start = self.id_xodr_hit
                    self.cp_type_start = self.cp_type
                    # Create helper stencil mesh
                    self.create_stencil(context, context.scene.cursor.location,
                        self.heading_start, self.snapped_start)
                    self.state = 'SELECT_END'
                    return {'RUNNING_MODAL'}
                if self.state == 'SELECT_END':
                    self.snapped_end = self.hit
                    cp_type_end = self.cp_type
                    # Create the final object
                    obj = self.create_object(context)
                    if self.snapped_start:
                        link_type = 'start'
                        helpers.create_object_xodr_links(context, obj, link_type,
                            self.id_xodr_start, self.cp_type_start)
                    if self.snapped_end:
                        link_type = 'end'
                        helpers.create_object_xodr_links(context, obj, link_type,
                            self.id_xodr_hit, cp_type_end)
                    # Remove stencil and go back to initial state to draw again
                    self.remove_stencil()
                    self.state = 'INIT'
                    return {'RUNNING_MODAL'}
        # Cancel step by step
        elif event.type in {'RIGHTMOUSE'} and event.value in {'RELEASE'}:
            # Back to beginning
            if self.state == 'SELECT_END':
                self.remove_stencil()
                self.state = 'INIT'
                return {'RUNNING_MODAL'}
            # Exit
            if self.state == 'SELECT_START':
                self.clean_up(context)
                return {'FINISHED'}
        # Exit immediately
        elif event.type in {'ESC'}:
            self.clean_up(context)
            return {'FINISHED'}
        # Zoom
        elif event.type in {'WHEELUPMOUSE'}:
            bpy.ops.view3d.zoom(mx=0, my=0, delta=1, use_cursor_init=False)
        elif event.type in {'WHEELDOWNMOUSE'}:
            bpy.ops.view3d.zoom(mx=0, my=0, delta=-1, use_cursor_init=True)
        elif event.type in {'MIDDLEMOUSE'}:
            if event.alt:
                bpy.ops.view3d.view_center_cursor()

        # Catch everything else arriving here
        return {'RUNNING_MODAL'}

    def calculate_heading_end(self, point_start, heading_start, point_end):
        vector_hdg = Vector((1.0, 0.0))
        vector_hdg.rotate(Matrix.Rotation(heading_start, 2))
        vector_start_end = (point_end - point_start).to_2d()
        adjacent = vector_start_end.to_2d().project(vector_hdg)
        # TODO make the heading ratio adjustable
        heading_ratio = 0.75
        vector_end = vector_start_end - heading_ratio * adjacent
        if vector_end.length == 0:
            return 0
        else:
            return vector_end.angle_signed(Vector((1.0, 0.0)))

    def invoke(self, context, event):
        # For operator state machine
        # possible states: {'INIT','SELECT_START', 'SELECT_END'}
        self.state = 'INIT'
        bpy.ops.object.select_all(action='DESELECT')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def clean_up(self, context):
        # Make sure stencil is removed
        self.remove_stencil()
        # Remove header text with 'None'
        context.workspace.status_text_set(None)
        # Set custom cursor
        bpy.context.window.cursor_modal_restore()
        # Make sure to exit edit mode
        if bpy.context.active_object:
            if bpy.context.active_object.mode == 'EDIT':
                bpy.ops.object.mode_set(mode='OBJECT')
        self.state = 'INIT'