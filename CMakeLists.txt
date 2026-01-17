cmake_minimum_required(VERSION 3.25)

project(pymergetic_common LANGUAGES CXX)

include(GNUInstallDirs)
include(FetchContent)

# Ensure Python development headers/targets are available for nanobind + modules.
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)

# Nanobind (tooling) - fetch so builds don't depend on a preinstalled CMake package.
FetchContent_Declare(
    nanobind
    GIT_REPOSITORY https://github.com/wjakob/nanobind.git
    GIT_TAG v2.9.2
)
FetchContent_MakeAvailable(nanobind)

# Some nanobind configurations don't automatically attach Python include dirs to
# its internal library target. Make this explicit so builds are robust across
# Python distributions (e.g. uv-managed Python).
foreach(_nb_tgt IN ITEMS nanobind nanobind-static nanobind_shared)
    if(TARGET ${_nb_tgt})
        target_link_libraries(${_nb_tgt} PRIVATE Python::Module)
    endif()
endforeach()

# --- 1) Fixed compile environment for all hybrid extensions ---
add_library(pymergetic_common_interface INTERFACE)
add_library(pymergetic::common_interface ALIAS pymergetic_common_interface)

target_compile_features(pymergetic_common_interface INTERFACE cxx_std_20)
set_target_properties(pymergetic_common_interface PROPERTIES
    INTERFACE_POSITION_INDEPENDENT_CODE ON
)

target_include_directories(pymergetic_common_interface INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)

# --- 2) Tooling: enforce nanobind usage via common ---
# NOTE: Do not hard-link an interface target against a specific nanobind CMake
# target name. When nanobind is brought in via FetchContent, the exported target
# name may differ from an installed `nanobindConfig.cmake` package.
# We only require `nanobind_add_module()` to exist for `pymergetic_add_extension()`.

# Convenience macro for extensions (prevents missed NB_SHARED, enforces env)
function(pymergetic_add_extension target_name)
    nanobind_add_module(${target_name} NB_SHARED ${ARGN})
    target_link_libraries(${target_name} PRIVATE pymergetic::common_interface)
    target_link_libraries(${target_name} PRIVATE Python::Module)
    # Ensure the nanobind shared library can be found at runtime from within wheels.
    if(APPLE)
        set_target_properties(${target_name} PROPERTIES
            BUILD_RPATH "@loader_path"
            INSTALL_RPATH "@loader_path"
        )
    else()
        set_target_properties(${target_name} PROPERTIES
            BUILD_RPATH "$ORIGIN"
            INSTALL_RPATH "$ORIGIN"
        )
    endif()
endfunction()

# --- 2b) Test extension (ensures the SDK build path works in CI) ---
pymergetic_add_extension(_test_internal
    src/bindings/test_module.cpp
)

# --- 3) Install headers + export CMake package ---
install(DIRECTORY src/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

install(TARGETS pymergetic_common_interface
    EXPORT PymergeticCommonTargets
)

install(TARGETS _test_internal
    LIBRARY DESTINATION pymergetic/common
    RUNTIME DESTINATION pymergetic/common
    ARCHIVE DESTINATION pymergetic/common
)

# If nanobind is built as a shared library, ship it alongside extensions so
# `libnanobind.so` is resolvable at runtime.
if(TARGET nanobind)
    install(TARGETS nanobind
        LIBRARY DESTINATION pymergetic/common
        RUNTIME DESTINATION pymergetic/common
        ARCHIVE DESTINATION pymergetic/common
    )
endif()

install(EXPORT PymergeticCommonTargets
    FILE pymergetic_commonTargets.cmake
    NAMESPACE pymergetic::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/pymergetic_common
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    "${CMAKE_CURRENT_LIST_DIR}/cmake/pymergetic_commonConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/pymergetic_commonConfig.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/pymergetic_common
)

install(FILES "${CMAKE_CURRENT_BINARY_DIR}/pymergetic_commonConfig.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/pymergetic_common
)


