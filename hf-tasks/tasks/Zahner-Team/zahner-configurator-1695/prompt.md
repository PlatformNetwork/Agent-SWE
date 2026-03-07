# Zahner-Team/zahner-configurator-1695

Fix texture mapping when a panel is rotated by 90° increments: do not swap atlas dimensions for odd rotations. Instead, swap the panel face dimensions used to compute texture repeat so the rotated sampling axes still cover the correct physical size. Ensure repeat values correspond to the panel’s actual dimensions after rotation and the atlas image size remains unchanged, preventing skewed or compressed textures.
