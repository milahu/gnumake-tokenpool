cmake_minimum_required(VERSION 3.14)
project(gnumake-tokenpool LANGUAGES CXX)

add_library(
    gnumake-tokenpool
    tokenpool-gnu-make-posix.cc
    # tokenpool-gnu-make-win32.cc # TODO: Add this file iff building on win32.
    tokenpool-gnu-make.cc)
target_include_directories(gnumake-tokenpool PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

option(GNUMAKE_TOKENPOOL_BUILD_TESTS "build gnumake-tokenpool tests" ON)

if (GNUMAKE_TOKENPOOL_BUILD_TESTS)
    # GoogleTest requires at least C++14
    set(CMAKE_CXX_STANDARD 14)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)

    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/releases/download/v1.15.2/googletest-1.15.2.tar.gz)
    # For Windows: Prevent overriding the parent project's compiler/linker settings
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)

    add_executable(gnumake-tokenpool-test tokenpool_test.cc)
    target_link_libraries(gnumake-tokenpool-test gnumake-tokenpool gtest_main)

    enable_testing()

    include(GoogleTest)
    gtest_discover_tests(gnumake-tokenpool-test)
endif ()
