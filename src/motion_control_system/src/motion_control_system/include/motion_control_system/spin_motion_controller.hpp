#ifndef MOTION_CONTROL_CONTROLLER_HPP
#define MOTION_CONTROL_CONTROLLER_HPP
#include "motion_control_system/motion_control_interface.hpp"

namespace motion_control_system {

    class SpinMotionController : public MotionController
    {
    private:
    public:
        void start() override;
        void stop() override;
    };  

}  // namespace motion_control_system

#endif  // MOTION_CONTROL_CONTROLLER_HPP
