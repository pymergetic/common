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

target_link_libraries(pymergetic_common_interface INTERFACE easybind::build_interface)

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

# --- 2b) Test extension (ensures the SDK build path works in CI) ---
pymergetic_add_extension(_test_internal
    src_cpp/pymergetic/common/test/__init__.cpp
)
target_link_libraries(_test_internal PRIVATE easybind::easybind)
set_target_properties(_test_internal PROPERTIES OUTPUT_NAME "__cpp_test__")

# --- 2c) Runtime net module (L4/L6 reference implementation) ---
pymergetic_add_extension(_internal
    src_cpp/pymergetic/common/__cpp__.cpp
    src_cpp/pymergetic/common/base/__init__.cpp
    src_cpp/pymergetic/common/codec/__init__.cpp
    src_cpp/pymergetic/common/exceptions/__init__.cpp
    src_cpp/pymergetic/common/header/__init__.cpp
    src_cpp/pymergetic/common/nb/__init__.cpp
    src_cpp/pymergetic/common/net/__init__.cpp
    src_cpp/pymergetic/common/objects/__init__.cpp
    src_cpp/pymergetic/common/runtime/__init__.cpp
    src_cpp/pymergetic/common/session/__init__.cpp
)
target_link_libraries(_internal PRIVATE easybind::easybind)
set_target_properties(_internal PROPERTIES OUTPUT_NAME "__cpp__")

# --- 3) Install headers + export CMake package ---
# Install C++ headers (mirrors the `pymergetic/...` include prefix)
install(DIRECTORY src_cpp/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

install(TARGETS pymergetic_common_interface
    EXPORT PymergeticCommonTargets
)

install(TARGETS _test_internal
    LIBRARY DESTINATION pymergetic/common
    RUNTIME DESTINATION pymergetic/common
    ARCHIVE DESTINATION pymergetic/common
)

install(TARGETS _internal
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


