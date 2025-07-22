import bpy
import os
import math
import sys
import mathutils

# To run the python file using CLI (Blender 3.0.1)
# ./blender -b -P animation_pose.py -- --name <name of folder containing .ply>

# Enable script auto-execution in Blender preferences
bpy.context.preferences.filepaths.use_scripts_auto_execute = True

# Remove the default cube if it exists
for o in bpy.context.scene.objects:
    if o.name == "Cube":
        bpy.ops.object.delete({"selected_objects": [o]}, use_global=False)

# Importing .ply files into the scene
def import_ply_files(directory):
    """
    Imports all .ply files from 'directory'. 
    Each imported object's name is taken from the filename 
    (e.g., '0000.ply' -> object.name = '0000').
    """

    file_list = os.listdir(directory)

    for file_name in file_list:
        if file_name.lower().endswith(".ply"):
            file_path = os.path.join(directory, file_name)
            try:
                # new blender versions
                bpy.ops.import_mesh.ply(filepath=file_path)
                imported_obj = bpy.context.selected_objects[0]

                # Rename object to the base of the filename, e.g. '0001'
                base_name = os.path.splitext(file_name)[0]
                imported_obj.name = base_name

                # Rotate the object if needed
                imported_obj.rotation_euler = (0, 0, 0)
                imported_obj.rotation_euler[0] = math.radians(-90)  # turn upright
                imported_obj.rotation_euler[2] = math.radians(180)

                imported_obj.location.z += 1
                
                # For Blender versions earlier than 3.0.1, use the following line to import PLY files:
                # bpy.ops.wm.ply_import(filepath=file_path, forward_axis='Z', up_axis='Y')

            except RuntimeError as err:
                print(f"Error importing {file_path}: {err}")

def create_shape_keys_for_frames():
    """
    Finds all objects named with integer numbers (e.g. '0000', '0001', '0002', ...).
    Uses the first as the 'main' object and adds the rest as shape keys.
    """

    # Gather all numbered objects in the scene (in "Collection" by default)
    all_objs = []
    main_collection = bpy.data.collections.get("Collection")
    if not main_collection:
        print("No collection named 'Collection' found. Exiting.")
        return

    for obj in main_collection.objects:
        try:
            int(obj.name)
            all_objs.append(obj)
        except ValueError:
            pass

    # Sort them by numeric name
    all_objs.sort(key=lambda o: int(o.name))

    if not all_objs:
        print("No numbered PLY objects found; cannot create shape keys.")
        return

    # The first object (e.g. "0000") will hold the shape keys
    main_obj = all_objs[0]
    bpy.ops.object.select_all(action='DESELECT')
    main_obj.select_set(True)
    bpy.context.view_layer.objects.active = main_obj

    # Add a Basis shape key if it doesn't already have one
    if not main_obj.data.shape_keys:
        bpy.ops.object.shape_key_add(from_mix=False)
        main_obj.data.shape_keys.key_blocks[-1].name = "Basis"

    # For each subsequent object, join it into main_obj as a new shape key
    for obj in all_objs[1:]:
        bpy.ops.object.select_all(action='DESELECT')
        main_obj.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = main_obj

        # Join Shapes creates a new shape key from the second selected object
        bpy.ops.object.join_shapes()

        # The newly added shape key will be the last in the shape key list
        sk = main_obj.data.shape_keys.key_blocks[-1]
        sk.name = f"Frame_{obj.name}"

    print("Shape-key creation complete. Main object:", main_obj.name)

def animate_shape_keys():
    """
    For each shape key 'Frame_0001', 'Frame_0002', etc., 
    set it to 1.0 on its matching frame, and 0.0 on other frames.
    """

    main_obj = None
    # Find the object that has shape keys (the "0000" object or whichever has shape_keys)
    for obj in bpy.data.objects:
        if obj.data and obj.data.shape_keys:
            main_obj = obj
            break

    if not main_obj:
        print("No object with shape keys found; cannot animate.")
        return

    shape_keys = main_obj.data.shape_keys.key_blocks

    # Collect the shape keys that follow the "Frame_XXXX" pattern
    frame_keys = []
    for sk in shape_keys:
        if sk.name.startswith("Frame_"):
            frame_str = sk.name.replace("Frame_", "")
            # e.g. sk.name = "Frame_0001" -> frame_str="0001" -> int(frame_str)=1
            try:
                num = int(frame_str)
                frame_keys.append((num, sk))
            except ValueError:
                pass

    # Sort shape keys by numeric suffix so we can iterate in order
    frame_keys.sort(key=lambda x: x[0])

    # Animate them: one shape key active per corresponding frame
    for frame_num, sk_block in frame_keys:
        # At this frame_num, set this shape key to 1.0, others 0.0
        bpy.context.scene.frame_set(frame_num)
        for sk in shape_keys:
            sk.value = 0.0
        sk_block.value = 1.0

        # Insert keyframes
        for sk in shape_keys:
            sk.keyframe_insert(data_path="value", frame=frame_num)

    # Adjust timeline range
    if frame_keys:
        min_frame = frame_keys[0][0]
        max_frame = frame_keys[-1][0]
        bpy.context.scene.frame_start = min_frame
        bpy.context.scene.frame_end = max_frame

    print("Shape-key animation set up from frame", bpy.context.scene.frame_start, "to", bpy.context.scene.frame_end)

def remove_extra_objects():
    """
    After shape keys have been created, the geometry from 
    all 'Frame_####' objects is already merged into the main mesh.
    We can remove them from the scene, or just hide them.
    """
    main_obj_name = "0000"
    main_obj = bpy.data.objects.get(main_obj_name)

    if not main_obj:
        # fallback: use any object that has shape keys
        for obj in bpy.data.objects:
            if obj.data and obj.data.shape_keys:
                main_obj = obj
                break

    # Gather the extra objects that are strictly numeric
    objs_to_remove = []
    for obj in bpy.data.collections["Collection"].objects:
        # skip the main object
        if obj == main_obj:
            continue

        # if name is numeric, or "Frame_..."
        try:
            int(obj.name)
            objs_to_remove.append(obj)
        except ValueError:
            pass

    # Remove them
    for obj in objs_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)
    print("Removed extra frame objects. Only main object remains.")

# Editing the scene of the blender environment
def scene_addition():

    # Adding a plane
    # bpy.ops.mesh.primitive_plane_add(size=20, enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))

    # # Changing the color of the plane
    # plane = bpy.data.objects.get("Plane")
    # if plane:
    #     plane_material = bpy.data.materials.new(name="PlaneMaterial")
    #     plane_material.diffuse_color = (0.112779, 1.0, 0.183889, 1.0)
    #     if plane.data.materials:
    #         plane.data.materials[0] = plane_material
    #     else:
    #         plane.data.materials.append(plane_material)
    # else:
    #     print("Plane object not found.")
    
    first_object = bpy.data.objects.get("0000")

    if first_object:
        material = bpy.data.materials.new(name="FirstObjectMaterial")

        # Changing the color of the SMPL Model
        # material.diffuse_color = (0.2, 0.799, 0.799, 1.0) # Green
        material.diffuse_color = (0.1, 0.1, 0.1, 1.0) # Grey

        if first_object.data.materials:
            first_object.data.materials[0] = material
        else:
            first_object.data.materials.append(material)

    # Changing the color of the world background
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)

# Adjusting the camera views of the camera object in the blender environment
def set_camera_view(view_type, LeftRight_adjust, Closeness_adjust, Height_adjust, Camera_angle, elevation_angle, azimuth_angle):

    # Get the camera object
    camera = bpy.data.objects.get("Camera")
    if not camera:
        print("Camera object not found.")
        return
    else:
        elevation_angle_degrees = elevation_angle
        azimuth_angle_degrees = azimuth_angle

    # Set camera rotation mode to Euler XYZ
    camera.rotation_mode = 'XYZ'

    # Get the target object
    target_object = bpy.data.objects.get("0000")
    if not target_object:
        print("Target object '0000' not found.")
        return

    # Get the location of the target object
    target_location = target_object.location

    # Define a zoom factor for specific views to zoom out
    zoom_out_views = ["front", "back", "left", "right", "upper-right", "upper-left", "front-left", "front-right"]
    zoom_factor = 2  # Adjust this factor as needed for desired zoom out effect

    # Modify adjustment parameters if the current view requires zooming out
    if view_type.lower() in zoom_out_views:
        adjusted_Distance = Closeness_adjust * zoom_factor
        adjusted_Height = Height_adjust * zoom_factor
    else:
        adjusted_Distance = Closeness_adjust
        adjusted_Height = Height_adjust

    # Adjust the camera angle if using a perspective camera
    if camera.data.type == 'PERSP':
        camera.data.angle = math.radians(Camera_angle)
    if elevation_angle is None and azimuth_angle is None:

    # Define camera parameters based on view type
        if view_type.lower() == "front":
            elevation_angle_degrees = 0
            azimuth_angle_degrees = 90
        elif view_type.lower() == "back":
            elevation_angle_degrees = 0
            azimuth_angle_degrees = 270
        elif view_type.lower() == "left":
            elevation_angle_degrees = 0
            azimuth_angle_degrees = 180
        elif view_type.lower() == "right":
            elevation_angle_degrees = 0
            azimuth_angle_degrees = 0
        elif view_type.lower() == "front-left":
            elevation_angle_degrees = 0
            azimuth_angle_degrees = 135  # Midway between front (180°) and left (90°)
        elif view_type.lower() == "front-right":
            elevation_angle_degrees = 0
            azimuth_angle_degrees = 45  # Midway between front (180°) and right (270°)
        elif view_type.lower() == "upper-left":
            elevation_angle_degrees = 45
            azimuth_angle_degrees = 135
        elif view_type.lower() == "upper-right":
            elevation_angle_degrees = 45
            azimuth_angle_degrees = 45
        else:
            print(f"Invalid view type '{view_type}'. Please choose a valid view.")
            return
    else:
        print("Custom angles provided.")
        elevation_angle_degrees = elevation_angle
        azimuth_angle_degrees = azimuth_angle

    # Convert angles to radians
    elev_rad = math.radians(elevation_angle_degrees)
    azim_rad = math.radians(azimuth_angle_degrees)

    # Calculate camera position in spherical coordinates
    R = adjusted_Distance
    dx = R * math.cos(elev_rad) * math.cos(azim_rad)
    dy = R * math.cos(elev_rad) * math.sin(azim_rad)
    dz = R * math.sin(elev_rad)

    # Adjust for LeftRight_adjust and Height_adjust
    dx += LeftRight_adjust
    dz += adjusted_Height

    camera.location = target_location + mathutils.Vector((dx, dy, dz))

    # Point camera at the target
    direction = target_location - camera.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()

# Exporting into .fbx format
def export_fbx(output_fbx_path):

    obj = bpy.data.objects["0000"]  # or whatever your main object's name is
    shape_keys = obj.data.shape_keys.key_blocks

    # Example of automatically setting up each shape key at its frame
    for sk_block in shape_keys:
        if sk_block.name.startswith("Frame_"):
            frame_str = sk_block.name.replace("Frame_", "")
            try:
                frame_num = int(frame_str)
            except ValueError:
                continue
            
            # 1) Move to "frame_num", set this shape key = 1.0, others = 0.0
            bpy.context.scene.frame_set(frame_num)
            for sk in shape_keys:
                sk.value = 0.0
            sk_block.value = 1.0

            # Keyframe all shape keys
            for sk in shape_keys:
                sk.keyframe_insert(data_path="value", frame=frame_num)

    # Find the object that has shape keys
    main_obj = bpy.data.objects.get("0000")  # or whichever name
    if not main_obj or not main_obj.data.shape_keys:
        # fallback: pick any object with shape keys
        for obj in bpy.data.objects:
            if obj.data and obj.data.shape_keys:
                main_obj = obj
                break

    if not main_obj:
        print("No object with shape keys found. Export aborted.")
        return

    # Select that object
    bpy.ops.object.select_all(action='DESELECT')
    main_obj.select_set(True)
    bpy.context.view_layer.objects.active = main_obj

    # only activate bake_anim is true
    # Export FBX with minimal settings recognized by older Blender
    bpy.ops.export_scene.fbx(
        filepath=output_fbx_path,
        bake_anim=True,
        bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=False,
    )
    print(f"Exported FBX to {output_fbx_path}")

# Exporting into .mp4 format
def export_video(output_path):
    # Set output file format and path
    bpy.context.scene.render.image_settings.file_format = 'FFMPEG'
    bpy.context.scene.render.ffmpeg.format = 'MPEG4'
    bpy.context.scene.render.ffmpeg.codec = 'H264'
    bpy.context.scene.render.filepath = output_path

    # Resolution settings
    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.resolution_percentage = 100

    # Set frames per second (adjustable)
    bpy.context.scene.render.fps = 27

    # Render the animation
    bpy.ops.render.render(animation=True)

def main():
    # Manually parse arguments
    args = sys.argv[sys.argv.index("--") + 1:]
    name = None

    for i, arg in enumerate(args):
        if arg == "--name" and i + 1 < len(args):
            name = args[i + 1]

    if not name:
        raise ValueError("The --name argument is required.")

    # Variables related to the folder location
    folder_name = "renders"

    # Folder location
    directory = f"./{folder_name}/{name}/"

    # Calling the function
    import_ply_files(directory)
    create_shape_keys_for_frames()
    animate_shape_keys()
    remove_extra_objects()
    scene_addition()

    # Parameters to adjust
    LeftRight_adjust = 0
    Closeness_adjust = 4
    Height_adjust = 1
    Camera_angle = 60

    # Open the file angleInput.txt and read the content
    with open('angleInput.txt', 'r') as file:
        # Read lines from the file and strip any trailing newline characters
        view_list = [line.strip() for line in file.readlines()]

    for view in view_list:
        if "Elevation:" in view and "Azimuth:" in view:
            # Parse the string to get the angles
            try:
                # Split the line by spaces and parse the angles
                parts = view.split()
                elevation_angle = float(parts[0].split(":")[1])
                azimuth_angle = float(parts[1].split(":")[1])
                print(f"Elevation: {elevation_angle}, Azimuth: {azimuth_angle}")
                
            except (IndexError, ValueError) as e:
                print("Error parsing angles:", e)
                continue
                
            set_camera_view(view, LeftRight_adjust, Closeness_adjust, Height_adjust, Camera_angle, elevation_angle, azimuth_angle)
            
            # Exporting the render
            output_path = f"./{folder_name}/{name}/{name}_custom_elevation{elevation_angle}_azimuth{azimuth_angle}.mp4"
            export_video(output_path)
        else:
            set_camera_view(view, LeftRight_adjust, Closeness_adjust, Height_adjust, Camera_angle, elevation_angle=None, azimuth_angle=None)

            # exporting fbx
            fbx_output_path = f"./{folder_name}/{name}/{name}_{view}_animation.fbx"
            export_fbx(fbx_output_path)

            # Exporting the render
            output_path = f"./{folder_name}/{name}/{name}_{view}_video.mp4"
            export_video(output_path)

if __name__ == "__main__":
    main()
