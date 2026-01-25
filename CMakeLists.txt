cmake_minimum_required(VERSION 3.25)

project(pymergetic_common LANGUAGES CXX)

include(GNUInstallDirs)
include(FetchContent)

# Easybind (shared registry for distributed bindings).
FetchContent_Declare(
    easybind
    SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/../easybind
)
FetchContent_MakeAvailable(easybind)

# --- 1) Fixed compile environment for all hybrid extensions ---
add_library(pymergetic_common_interface INTERFACE)
add_library(pymergetic::common_interface ALIAS pymergetic_common_interface)

target_link_libraries(pymergetic_common_interface INTERFACE
    $<BUILD_INTERFACE:easybind::build_interface>
)

target_include_directories(pymergetic_common_interface INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src_cpp>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)

# --- 2) Tooling: build macro lives in easybind ---

# Convenience macro for extensions (prevents missed NB_SHARED, enforces env)
function(pymergetic_add_extension target_name)
    easybind_add_extension(${target_name} ${ARGN})
    target_link_libraries(${target_name} PRIVATE pymergetic::common_interface)
endfunction()

pymergetic_add_extension(common_sysinfo_internal
    src_cpp/pymergetic/common/sysinfo/__cpp__.cpp
)
target_link_libraries(common_sysinfo_internal PRIVATE easybind::easybind)
if(DEFINED SKBUILD_PROJECT_VERSION_FULL)
    set(_common_build_version "${SKBUILD_PROJECT_VERSION_FULL}")
elseif(DEFINED SKBUILD_PROJECT_VERSION)
    set(_common_build_version "${SKBUILD_PROJECT_VERSION}")
elseif(DEFINED ENV{SKBUILD_PROJECT_VERSION})
    set(_common_build_version "$ENV{SKBUILD_PROJECT_VERSION}")
else()
    set(_common_build_version "0.0.0")
endif()
target_compile_definitions(common_sysinfo_internal PRIVATE
    EASYBIND_BUILD_VERSION="${_common_build_version}"
)
set_target_properties(common_sysinfo_internal PROPERTIES
    OUTPUT_NAME "__cpp__"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/pymergetic/common/sysinfo"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/pymergetic/common/sysinfo"
)
if(APPLE)
    set_target_properties(common_sysinfo_internal PROPERTIES
        BUILD_RPATH "@loader_path/..;@loader_path/../../easybind"
        INSTALL_RPATH "@loader_path/..;@loader_path/../../easybind"
    )
else()
    set_target_properties(common_sysinfo_internal PROPERTIES
        BUILD_RPATH "$ORIGIN/..;$ORIGIN/../../easybind"
        INSTALL_RPATH "$ORIGIN/..;$ORIGIN/../../easybind"
    )
endif()

pymergetic_add_extension(common_internal
    src_cpp/pymergetic/common/__cpp__.cpp
)
target_link_libraries(common_internal PRIVATE easybind::easybind)
target_compile_definitions(common_internal PRIVATE
    EASYBIND_BUILD_VERSION="${_common_build_version}"
)
set_target_properties(common_internal PROPERTIES
    OUTPUT_NAME "__cpp__"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/pymergetic/common"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/pymergetic/common"
)
if(APPLE)
    set_target_properties(common_internal PROPERTIES
        BUILD_RPATH "@loader_path/..;@loader_path/../..;@loader_path/../../easybind"
        INSTALL_RPATH "@loader_path/..;@loader_path/../..;@loader_path/../../easybind"
    )
else()
    set_target_properties(common_internal PROPERTIES
        BUILD_RPATH "$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../easybind"
        INSTALL_RPATH "$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../easybind"
    )
endif()

# --- 3) Install headers + export CMake package ---
# Install C++ headers (mirrors the `pymergetic/...` include prefix)
install(DIRECTORY src_cpp/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

install(TARGETS pymergetic_common_interface
    EXPORT PymergeticCommonTargets
)

install(TARGETS common_sysinfo_internal
    LIBRARY DESTINATION pymergetic/common/sysinfo
    RUNTIME DESTINATION pymergetic/common/sysinfo
    ARCHIVE DESTINATION pymergetic/common/sysinfo
)

install(TARGETS common_internal
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


