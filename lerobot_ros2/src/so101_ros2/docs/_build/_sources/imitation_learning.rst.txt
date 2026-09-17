Imitation Learning
==================

The SO101 ROS 2 workspace integrates teleoperation, recording, and dataset
conversion tools so you can generate demonstrations for downstream imitation
learning pipelines.

Prerequisites
---------------------
- A working SO101 ROS 2 setup with leader and follower communication verified. Follow
  the `getting started guide <./getting_started.html>`_ to prepare and launch the
  system.
- Bridge and camera configurations updated to match your hardware setup.
- (Optional) NVIDIA Isaac Sim 5.0 installed for simulator-based teleoperation. You can use the source code `installation guide <https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/source_installation.html>`_.

Real teleoperation
------------------
Launch the bridge with the physical leader and follower hardware::

   ros2 launch so101_bringup so101_teleoperate.launch.py mode:=real display:=true

Monitor the logs for connection issues and confirm that the follower mirrors the
leader motions while RViz visualises the joint states and cameras feeds.

.. video:: ../media/video/il_real_teleop.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Real teleoperation video

.. video:: ../media/video/il_real_teleop2.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Real teleoperation video 2

Isaac Sim teleoperation
-----------------------
Use the simulator workflow to stream demonstrations into Isaac Sim.

1. Bringup IsaacSim in one terminal::

      ${ISAACSIM_PATH}/isaac-sim.sh

2. Load your ready-made usd file or use the provided example scene located at ``so101_description/usd/so101_new_calib.usd``.

3. Launch in a second terminal the teleoperation pipeline connected to the Isaac transport topics::

      ros2 launch so101_bringup so101_teleoperate.launch.py mode:=isaac display:=true

4. Start simulation.

This reuses the teleoperation pipeline while switching the interfaces to the Isaac transport topics so you can stream demonstrations from the leader arm directly into the simulator using Isaac ROS 2 Bridge.

You should now be able to move the leader arm and see the follower in IsaacSim mimicking its motions in real time and RViz which visualises the follower cameras and follower state comparing to the leader state.


.. video:: ../media/video/il_isaac_teleop.mp4
   :width: 600
   :height: 300
   :muted:
   :align: center
   :alt: Isaac Sim teleoperation video 2

.. video:: ../media/video/il_isaac_teleop2.mp4
   :width: 600
   :height: 300
   :muted:
   :align: center
   :alt: Isaac Sim teleoperation video 2


Record demonstrations with ``system_data_recorder``
-----------------------------------------------------

The workspace ships with launch files for the
``system_data_recorder`` package to capture rosbag2 datasets.

1. Adjust ``so101_bringup/config/so101_sdr.yaml`` to list the topics you want to
   record, set ``bag_name_prefix`` and ``copy_destination``.
2. Start your teleoperation session (real or Isaac).
3. Launch the recorder::

       ros2 launch so101_bringup so101_record.launch.py

4. Drive the lifecycle transitions from another terminal::

       ros2 lifecycle set /sdr configure
       ros2 lifecycle set /sdr activate

5. Stop the recording when the demonstration is complete::

       ros2 lifecycle set /sdr deactivate
       ros2 lifecycle set /sdr shutdown

Using the Keyboard Commander
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For improved usability, the ``system_data_recorder`` package includes an
``SDRKeyboardCommander`` node that sends lifecycle transition requests to the
``/sdr`` node based on keyboard input.

This allows you to control the recorder without manually typing lifecycle
commands.

Running the Commander
^^^^^^^^^^^^^^^^^^^^^

1. In one terminal, launch the recorder:

   .. code-block:: bash

      ros2 launch so101_bringup so101_record.launch.py

2. In a second terminal, start the keyboard commander:

   .. code-block:: bash

      ros2 run system_data_recorder sdr_commander

Keyboard Controls
^^^^^^^^^^^^^^^^^

Once running, the commander listens for key presses and triggers the
corresponding lifecycle transitions on the ``/sdr`` node.

=================  ==============================  ===============================
Key                Action                          Lifecycle Transition
=================  ==============================  ===============================
``c``              Configure                       ``CONFIGURE``
``a``              Activate (start recording)      ``ACTIVATE``
``d``              Deactivate (pause recording)    ``DEACTIVATE``
``l``              Cleanup                         ``CLEANUP``
``s``              Shutdown                        ``SHUTDOWN``
``g``              Get State                       Query and print state
``h``              Help                            Print help menu
``q``              Quit                            Exit commander node
=================  ==============================  ===============================

The resulting rosbag2 dataset is saved under the directory specified in
``copy_destination`` with the prefix from ``bag_name_prefix``.

You can inspect the produced bag using:

.. code-block:: bash

   ros2 bag info <bag_path>

For additional options and advanced usage, refer to the
`system_data_recorder documentation <https://github.com/nimiCurtis/system_data_recorder>`_ .

A successful recording session should produce output similar to:

.. video:: ../media/video/il_sdr.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Data recording

.. video:: ../media/video/il_sdr2.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Data recording 2

Convert rosbag2 datasets
------------------------
Convert captured rosbag2 files into Lerobot datasets with the
`so101_rosbag2lerobot_dataset <https://github.com/nimiCurtis/so101_rosbag2lerobot_dataset>`_ utilities.

1. First install the package:

.. code-block:: bash

   conda activate lerobot_ros2
   git clone https://github.com/nimiCurtis/so101_rosbag2lerobot_dataset.git
   cd so101_rosbag2lerobot_dataset
   pip install so101_rosbag2lerobot_dataset

2. Prepare a YAML configuration describing the topics and output directory. An example config is shown in the package config directory.

.. code-block:: bash

   so101-rosbag2lerobot --config <path_to_your_config.yaml>

3. Inspect results with ``lerobot-dataset-viz`` or online with `Huggingface Lerobot Dataset Visualizer <https://huggingface.co/spaces/lerobot/visualize_dataset>`_.

.. video:: ../media/video/il_data_conversion2.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Data conversion video2


Training
----------------------

Finetune a VLA model on the collected dataset using directly the ``lerobot`` package.
Check out the official tutorials on `imitation learning with lerobot <https://huggingface.co/docs/lerobot/il_robots#train-a-policy>`_.


Deployment
------------------------

Once trained, deploy the VLA policy in place of the leader commands.

.. attention::

   Currently only SmolVla is supported. Other policies may be added in future releases.

Configuration
~~~~~~~~~~~~~

1. Update the policy parameters in ``so101_ros2_bridge/config/so101_policy_params.yaml`` to
   point to your trained model checkpoint and adjust any inference settings.

   For example:

   .. code-block:: yaml

      /**:
      ros__parameters:
         # Sync / timing
         inference_rate: 1.0          # Hz, how often to run policy
         inference_delay: 0.5        # sec, delay of inference
         publish_rate: 25.0           # Hz, how often to publish JointState commands
         sync.queue_size: 20               # message_filters queue_size
         sync.slop: 0.1                  # ApproximateTimeSynchronizer slop [sec]

         # General policy parameters
         policy_name: "smolvla"
         device: cuda:0
         checkpoint_path: "<your abs path to the ckpt dir>/pretrained_model"  # Default checkpoint path
         task: "<your task description here>" # e.g "Pick the cube and place it in the bowl."

2. Update the input/output parameters in ``so101_ros2_bridge/config/policies/io.yaml`` to match your setup.

   For example:

   .. code-block:: yaml

      observations:

         observation.images.camera1:
            topic: "/follower/cam_front/image_raw"
            msg_type: "sensor_msgs/msg/Image"

         observation.images.camera2:
            topic: "/static_camera/cam_side/color/image_raw"
            msg_type: "sensor_msgs/msg/Image"

         observation.state:
            topic: "/follower/joint_states"
            msg_type: "sensor_msgs/msg/JointState"

      action:
         topic: "/leader/joint_states"
         msg_type: "sensor_msgs/msg/JointState"

   .. attention::

      Ensure that the observations and the action keys (e.g. "observation.images.camera1", "action") are corresponding to the dataset features structure.

3. Update the specific policy parameters in ``so101_ros2_bridge/config/policies/<policy_name>.yaml`` as needed.

   For example, for smolvla:

   .. code-block:: yaml

      # Specific smolvla policy configuration
      lpf_filtering:
      enable: True # Enable or disable low-pass filtering
      alpha: 0.1 # Smoothing factor for low-pass filter [0.0 - 1.0], lower values mean more smoothing


Key Parameters
^^^^^^^^^^^^^^

``so101_policy_params.yaml`` exposes several key parameters for tuning the policy behavior:

- **inference_rate**: The rate at which the policy is invoked (Hz). Depend on hardware capabilities and desired responsiveness.
- **inference_delay**: The time interval (sec) between the model receiving an input and producing the corresponding output. This value should be empirically measured and configured to match the specific model's performance. It is crucial for ensuring smooth and timely responses. Affects the starting action index to slice the predicted chunk.
- **publish_rate**: The rate at which the policy publishes actions (Hz). This should be compatible with the follower controller update rate and the inference rate. The higher value of publish_rate the faster action buffer/chunk will be processed. However, very high publish_rate with low inference_rate may lead to repeated actions being sent, and vibration of the arm.
- **sync.queue_size**: The size of the message filter queue for synchronizing topics.
- **sync.slop**: The slop time for the approximate time synchronizer (sec). This defines the maximum time difference allowed between messages to be considered synchronized. It should be set based on the expected message arrival times and system latency.

Policy Lifecycle Node
~~~~~~~~~~~~~~~~~~~~~

The policy lifecycle node is responsible for managing the lifecycle of the policy. It handles transitions between different states.

=================  ==============================================================
Transition         Description
=================  ==============================================================
CONFIGURE          Loads the policy model and prepares it for inference.
ACTIVATE           Starts the inference loop, allowing the policy to control the follower arm.
DEACTIVATE         Stops the inference loop, pausing policy control. Current state is retained.
CLEANUP            Resets the node to an unconfigured state.
SHUTDOWN           Cleans up resources and prepares for shutdown.
=================  ==============================================================

For example, to configure and activate the policy node, use the following commands:

   .. code-block:: bash
      ros2 lifecycle set /policy_runner configure
      ros2 lifecycle set /policy_runner activate


Real Inference
~~~~~~~~~~~~~~

Launch the teleoperation pipeline in **real** mode using **policy** expert instead of human.

.. code-block:: bash

   ros2 launch so101_bringup so101_teleoperate.launch.py mode:=real expert:=policy display:=true

The launch file will start follower bridge, cameras, policy lifecycle node and RViz (if `display:=true`). The policy node will subscribe to the synced follower camera topics and joint states and will do nothing until configured and activated.

In another terminal, configure and activate the policy node:

.. code-block:: bash
   ros2 lifecycle set /policy_runner configure
   ros2 lifecycle set /policy_runner activate

.. attention::
   Configure transition can take some time depending on the model size and hardware.

Then the follower arm should start moving according to the policy's predictions based on the observations and the specified task.

.. video:: ../media/video/il_real_inference.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Real inference video


Isaac Sim Inference
~~~~~~~~~~~~~~~~~~~

1. Bringup IsaacSim in one terminal::

      ${ISAACSIM_PATH}/isaac-sim.sh

2. Load your ready-made usd file or use the provided example scene located at ``so101_description/usd/so101_new_calib.usd``.

3. Launch the teleoperation pipeline in **isaac** mode using **policy** expert.

   .. code-block:: bash

      ros2 launch so101_bringup so101_teleoperate.launch.py mode:=isaac expert:=policy display:=true

   The workflow is similar to the real inference case, but the policy node will subscribe to the synced Isaac transport topics instead.

4. Start simulation.

5. In another terminal, configure and activate the policy node, once configured and activated, the follower in IsaacSim should start moving according to the policy's predictions.

.. video:: ../media/video/il_isaac_inference.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Isaac Sim inference video

.. video:: ../media/video/il_isaac_inference2.mp4
   :width: 600
   :height: 400
   :muted:
   :align: center
   :alt: Isaac Sim inference video 2
