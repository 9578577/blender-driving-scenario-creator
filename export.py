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

from scenariogeneration import xosc
from scenariogeneration import xodr
from scenariogeneration import ScenarioGenerator

from math import pi

import pathlib
import subprocess


class DSC_OT_export(bpy.types.Operator):
    bl_idname = 'dsc.export_driving_scenario'
    bl_label = 'Export driving scenario'
    bl_description = 'Export driving scenario as OpenDRIVE, OpenSCENARIO and Mesh (e.g. OSGB, FBX, glTF 2.0)'

    directory: bpy.props.StringProperty(
        name='Export directory', description='Target directory for export.')

    mesh_file_type : bpy.props.EnumProperty(
        items=(('fbx', '.fbx', '', 0),
               ('gltf', '.gltf', '', 1),
               ('osgb', '.osgb', '', 2),
              ),
        default='osgb',
    )

    dsc_export_filename = 'export'

    @classmethod
    def poll(cls, context):
        if 'OpenDRIVE' in bpy.data.collections:
            return True
        else:
            return False

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Mesh file:")
        row.prop(self, "mesh_file_type", expand=True)

    def execute(self, context):
        self.export_vehicle_models()
        self.export_scenegraph_file()
        self.export_openscenario(context, self.directory)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def export_scenegraph_file(self):
        '''
            Export the scene mesh to file
        '''
        file_path = pathlib.Path(self.directory) / 'scenegraph' / 'export.suffix'
        file_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.object.select_all(action='SELECT')
        if 'OpenSCENARIO' in bpy.data.collections:
            for obj in bpy.data.collections['OpenSCENARIO'].all_objects:
                obj.select_set(False)
        self.export_mesh(file_path)
        bpy.ops.object.select_all(action='DESELECT')

    def export_vehicle_models(self):
        '''
            Export vehicle models to files.
        '''
        model_dir = pathlib.Path(self.directory) / 'models' / 'car.obj'
        model_dir.parent.mkdir(parents=True, exist_ok=True)
        catalog_path = pathlib.Path(self.directory) / 'catalogs' / 'vehicles' / 'VehicleCatalog.xosc'
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        # Select a car
        bpy.ops.object.select_all(action='DESELECT')
        if 'OpenSCENARIO' in bpy.data.collections:
            if 'Models' in bpy.data.collections['OpenSCENARIO'].children:
                for obj in bpy.data.collections['OpenSCENARIO'].children['Models'].all_objects:
                    model_path = pathlib.Path(self.directory) / 'models' / str(obj.name + '.obj')
                    obj.hide_viewport = False
                    obj.select_set(True)
                    self.export_mesh(model_path)
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.hide_viewport = True
                    self.convert_to_osgb(model_path)
                    # Add vehicle to vehicle catalog
                    # TODO store in and read parameters from object
                    bounding_box = xosc.BoundingBox(2,5,1.8,2.0,0,0.9)
                    axle_front = xosc.Axle(0.523599,0.8,1.554,2.98,0.4)
                    axle_rear = xosc.Axle(0,0.8,1.525,0,0.4)
                    car = xosc.Vehicle(obj.name,xosc.VehicleCategory.car,
                        bounding_box,axle_front,axle_rear,69,10,10)
                    car.add_property_file('../models/' + obj.name + '.' + self.mesh_file_type)
                    car.add_property('control','internal')
                    car.add_property('model_id','0')
                    # Dump vehicle to catalog
                    car.dump_to_catalog(catalog_path,'VehicleCatalog',
                        'DSC vehicle catalog','Blender Driving Scenario Creator')
                    break

    def export_mesh(self, file_path):
        '''
            Export a mesh to file
        '''
        if self.mesh_file_type == 'osgb':
            # Since Blender has no native .osgb support export .obj and then convert
            file_path = file_path.with_suffix('.obj')
            file_path.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.export_scene.obj(filepath=str(file_path), check_existing=True,
                                     filter_glob='*.obj,*.mtl', use_selection=True, use_animation=False,
                                     use_mesh_modifiers=True, use_edges=True, use_smooth_groups=False,
                                     use_smooth_groups_bitflags=False, use_normals=True, use_uvs=True,
                                     use_materials=True, use_triangles=False, use_nurbs=False,
                                     use_vertex_groups=False, use_blen_objects=True, group_by_object=False,
                                     group_by_material=False, keep_vertex_order=False, global_scale=1.0,
                                     path_mode='RELATIVE', axis_forward='-Z', axis_up='Y')
            self.convert_to_osgb(file_path)
        elif self.mesh_file_type == 'fbx':
            file_path = file_path.with_suffix('.fbx')
            file_path.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.export_scene.fbx(filepath=str(file_path), check_existing=True, filter_glob='*.fbx',
                                     use_selection=True, use_active_collection=False, global_scale=1.0,
                                     apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                                     use_space_transform=True, bake_space_transform=False,
                                     object_types={'ARMATURE', 'CAMERA', 'EMPTY', 'LIGHT', 'MESH', 'OTHER'},
                                     use_mesh_modifiers=True, use_mesh_modifiers_render=True,
                                     mesh_smooth_type='OFF', use_subsurf=False, use_mesh_edges=False,
                                     use_tspace=False, use_custom_props=False, add_leaf_bones=True,
                                     primary_bone_axis='Y', secondary_bone_axis='X',
                                     use_armature_deform_only=False, armature_nodetype='NULL',
                                     bake_anim=True, bake_anim_use_all_bones=True,
                                     bake_anim_use_nla_strips=True, bake_anim_use_all_actions=True,
                                     bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                                     bake_anim_simplify_factor=1.0, path_mode='AUTO',
                                     embed_textures=False, batch_mode='OFF', use_batch_own_dir=True,
                                     use_metadata=True, axis_forward='-Z', axis_up='Y')
        elif self.mesh_file_type == 'gltf':
            file_path = file_path.with_suffix('.gltf')
            file_path.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.export_scene.gltf(filepath=str(file_path), check_existing=True,
                                      export_format='GLTF_EMBEDDED', ui_tab='GENERAL', export_copyright='',
                                      export_image_format='AUTO', export_texture_dir='',
                                      export_texcoords=True, export_normals=True,
                                      export_draco_mesh_compression_enable=False,
                                      export_draco_mesh_compression_level=6,
                                      export_draco_position_quantization=14,
                                      export_draco_normal_quantization=10,
                                      export_draco_texcoord_quantization=12,
                                      export_draco_color_quantization=10,
                                      export_draco_generic_quantization=12, export_tangents=False,
                                      export_materials='EXPORT', export_colors=True, use_mesh_edges=False,
                                      use_mesh_vertices=False, export_cameras=False, export_selected=False,
                                      use_selection=True, use_visible=False, use_renderable=False,
                                      use_active_collection=False, export_extras=False, export_yup=True,
                                      export_apply=False, export_animations=True, export_frame_range=True,
                                      export_frame_step=1, export_force_sampling=True,
                                      export_nla_strips=True, export_def_bones=False,
                                      export_current_frame=False, export_skins=True,
                                      export_all_influences=False, export_morph=True,
                                      export_morph_normal=True, export_morph_tangent=False,
                                      export_lights=False, export_displacement=False,
                                      will_save_settings=False, filter_glob='*.glb;*.gltf')

    def convert_to_osgb(self, input_file_path):
        try:
            subprocess.run(['osgconv', str(input_file_path), str(input_file_path.with_suffix('.osgb'))])
        except FileNotFoundError:
            self.report({'ERROR'}, 'Executable \"osgconv\" required to produce .osgb scenegraph file. '
                'Try installing openscenegraph.')

    def export_openscenario(self, context, directory):
        # OpenDRIVE (referenced by OpenSCENARIO)
        xodr_path = pathlib.Path(self.directory) / 'xodr' / (self.dsc_export_filename + '.xodr')
        xodr_path.parent.mkdir(parents=True, exist_ok=True)
        odr = xodr.OpenDrive('blender_dsc')
        roads = []
        # Create OpenDRIVE roads from object collection
        for obj in bpy.data.collections['OpenDRIVE'].all_objects:
            if 'road' in obj.name:
                if obj['geometry'] == 'line':
                    planview = xodr.PlanView()
                    planview.set_start_point(obj['geometry_x'],
                        obj['geometry_y'],obj['geometry_hdg_start'])
                    line = xodr.Line(obj['geometry_length'])
                    planview.add_geometry(line)
                    # Create simple lanes
                    lanes = xodr.Lanes()
                    lanesection = xodr.LaneSection(0,xodr.standard_lane())
                    lanesection.add_left_lane(xodr.standard_lane(rm=xodr.STD_ROADMARK_SOLID))
                    lanesection.add_right_lane(xodr.standard_lane(rm=xodr.STD_ROADMARK_SOLID))
                    lanes.add_lanesection(lanesection)
                    road = xodr.Road(obj['id_xodr'],planview,lanes)
                if obj['geometry'] == 'arc':
                    planview = xodr.PlanView()
                    planview.set_start_point(obj['geometry_x'],
                        obj['geometry_y'],obj['geometry_hdg_start'])
                    arc = xodr.Arc(obj['geometry_curvature'],
                        angle=obj['geometry_angle'])
                    planview.add_geometry(arc)
                    # Create simple lanes
                    lanes = xodr.Lanes()
                    lanesection = xodr.LaneSection(0,xodr.standard_lane())
                    lanesection.add_left_lane(xodr.standard_lane(rm=xodr.STD_ROADMARK_SOLID))
                    lanesection.add_right_lane(xodr.standard_lane(rm=xodr.STD_ROADMARK_SOLID))
                    lanes.add_lanesection(lanesection)
                    road = xodr.Road(obj['id_xodr'],planview,lanes)
                # Add road level linking
                if 'link_predecessor' in obj:
                    element_type = self.get_element_type_by_id(obj['link_predecessor'])
                    if obj['link_predecessor_cp'] == 'cp_start':
                        cp_type = xodr.ContactPoint.start
                    elif obj['link_predecessor_cp'] == 'cp_end':
                        cp_type = xodr.ContactPoint.end
                    else:
                        cp_type = None
                    road.add_predecessor(element_type, obj['link_predecessor'], cp_type)
                if 'link_successor' in obj:
                    element_type = self.get_element_type_by_id(obj['link_successor'])
                    if obj['link_successor_cp'] == 'cp_start':
                        cp_type = xodr.ContactPoint.start
                    elif obj['link_successor_cp'] == 'cp_end':
                        cp_type = xodr.ContactPoint.end
                    else:
                        cp_type = None
                    road.add_successor(element_type, obj['link_successor'], cp_type)
                print('Add road with ID', obj['id_xodr'])
                odr.add_road(road)
                roads.append(road)
        # Add lane level linking for all roads
        # TODO: Improve performance by exploiting symmetry
        for road in roads:
            if road.predecessor:
                road_pre = self.get_road_by_id(roads, road.predecessor.element_id)
                if road_pre:
                    xodr.create_lane_links(road, road_pre)
            if road.successor:
                road_suc = self.get_road_by_id(roads, road.successor.element_id)
                if road_suc:
                    xodr.create_lane_links(road, road_suc)
        # Create OpenDRIVE junctions from object collection
        num_junctions = 0
        for obj in bpy.data.collections['OpenDRIVE'].all_objects:
            if 'junction' in obj.name:
                if not len(obj['incoming_roads']) == 4:
                    self.report({'ERROR'}, 'Junction must have 4 connected roads.')
                    break
                incoming_roads = []
                angles = []
                junction_id = obj['id_xodr']
                # Create junction roads based on incoming road angles (simple 4-way for now)
                for idx in range(4):
                    angles.append(idx * 2 * pi / len(obj['incoming_roads']))
                # 0 angle road must point in 'right' direction
                incoming_roads.append(xodr.get_road_by_id(roads, obj['incoming_roads']['cp_right']))
                incoming_roads.append(xodr.get_road_by_id(roads, obj['incoming_roads']['cp_up']))
                incoming_roads.append(xodr.get_road_by_id(roads, obj['incoming_roads']['cp_left']))
                incoming_roads.append(xodr.get_road_by_id(roads, obj['incoming_roads']['cp_down']))
                # Create connecting roads and link them to incoming roads
                junction_roads = xodr.create_junction_roads_standalone(angles, 3.4, junction_id,
                    spiral_part=0.1, arc_part=0.8, startnum=1000+6*num_junctions)
                i = 0
                for j in range(len(incoming_roads) - 1):
                    for k in range(j + 1, len(incoming_roads)):
                        # FIXME this will create problems when a single road is
                        # connected to a junction twice
                        if incoming_roads[j].predecessor:
                            if incoming_roads[j].predecessor.element_id == junction_id:
                                cp_type_j = xodr.ContactPoint.start
                        if incoming_roads[j].successor:
                            if incoming_roads[j].successor.element_id == junction_id:
                                cp_type_j = xodr.ContactPoint.end
                        if incoming_roads[k].predecessor:
                            if incoming_roads[k].predecessor.element_id == junction_id:
                                cp_type_k = xodr.ContactPoint.start
                        if incoming_roads[k].successor:
                            if incoming_roads[k].successor.element_id == junction_id:
                                cp_type_k = xodr.ContactPoint.end
                        # Link incoming with connecting road
                        junction_roads[i].add_predecessor(
                            xodr.ElementType.road, incoming_roads[j].id, cp_type_j)
                        # FIXME is redundant lane linking needed?
                        xodr.create_lane_links(junction_roads[i], incoming_roads[j])
                        junction_roads[i].add_successor(
                            xodr.ElementType.road, incoming_roads[k].id, cp_type_k)
                        # FIXME is redundant lane linking needed?
                        xodr.create_lane_links(junction_roads[i], incoming_roads[k])
                        i += 1
                # Finally create the junction
                junction = xodr.create_junction(
                    junction_roads, junction_id, incoming_roads, 'junction_' + str(junction_id))
                num_junctions += 1
                print('Add junction with ID', junction_id)
                odr.add_junction(junction)
                for road in junction_roads:
                    odr.add_road(road)
        odr.adjust_startpoints()
        odr.write_xml(str(xodr_path))

        # OpenSCENARIO
        xosc_path = pathlib.Path(self.directory) / 'xosc' / (self.dsc_export_filename + '.xosc')
        xosc_path.parent.mkdir(parents=True, exist_ok=True)
        init = xosc.Init()
        entities = xosc.Entities()
        if 'OpenSCENARIO' in bpy.data.collections:
            for obj in bpy.data.collections['OpenSCENARIO'].all_objects:
                # Filter out Model templates
                if 'Models' == obj.users_collection[0].name:
                    break
                if 'car' in obj.name:
                    car_name = obj.name
                    print('Add car with ID', obj['id_xosc'])
                    entities.add_scenario_object(car_name,xosc.CatalogReference('VehicleCatalog','car'))
                    init.add_init_action(car_name, xosc.TeleportAction(
                        xosc.WorldPosition(x=obj['x'], y=obj['y'], z=obj['z'], h=obj['hdg'])))
                    init.add_init_action(car_name, xosc.AbsoluteSpeedAction(
                        30, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 1)))
                    init.add_init_action(car_name, xosc.RelativeLaneChangeAction(0, car_name,
                        xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.rate, 1)))

        road = xosc.RoadNetwork(str(xodr_path),'./scenegraph/export.' + self.mesh_file_type)
        catalog = xosc.Catalog()
        catalog.add_catalog('VehicleCatalog','../catalogs/vehicles')
        storyboard = xosc.StoryBoard(init,stoptrigger=xosc.ValueTrigger('start_trigger ', 3, xosc.ConditionEdge.none,xosc.SimulationTimeCondition(13,xosc.Rule.greaterThan),'stop'))
        scenario = xosc.Scenario('dsc_scenario','blender_dsc',xosc.ParameterDeclarations(),entities,storyboard,road,catalog)
        scenario.write_xml(str(xosc_path))

    def get_element_type_by_id(self, id):
        '''
            Return element type of an OpenDRIVE element with given ID
        '''
        for obj in bpy.data.collections['OpenDRIVE'].all_objects:
            if 'road' in obj.name:
                if obj['id_xodr'] == id:
                    return xodr.ElementType.road
            elif 'junction' in obj.name:
                if obj['id_xodr'] == id:
                    return xodr.ElementType.junction

    def get_road_by_id(self, roads, id):
        '''
            Return road with given ID
        '''
        for road in roads:
            if road.id == id:
                return road
        print('WARNING: No road with ID {} found. Maybe a junction?'.format(id))
        return None