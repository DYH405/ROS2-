#!/bin/bash
# Record ROS2 bag for 30 seconds
# Usage: ./record_30s.sh
#DATE=$(date +%Y%m%d_%H%M%S)
#DURATION=30
#source /opt/ros/humble/setup.bash
#cd ~/ros2_ws/bag_data
#Qecho "Recording bag for $DURATION seconds..."
#timeout 3 ros2 bag record -o ./bag_ /scan /tf /tf_static /cmd_vel /odom
#echo "Bag recording completed."
#!/bin/bash

DURATION=30
DATE=$(date +%Y%m%d_%H%M%S)

source /opt/ros/humble/setup.bash

BAG_ROOT="$HOME/ros2_ws/bag_data"
mkdir -p "$BAG_ROOT"
cd "$BAG_ROOT" || exit 1

echo "Recording bag for ${DURATION} seconds..."

timeout --signal=INT --kill-after=5s --foreground "${DURATION}s" \
ros2 bag record \
-o "bag_${DATE}" \
/scan \
/tf \
/tf_static \
/cmd_vel \
/odom \
/plan

echo "Bag recording completed."