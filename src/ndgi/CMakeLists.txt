add_library(ndgi STATIC
  ndgi_graph.cc
  ndgi_store.cc
)
target_include_directories(ndgi PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/..)
target_link_libraries(ndgi PUBLIC trit_lib ternary_search_tree)
target_compile_options(ndgi PRIVATE -Wall -Wextra -Werror -O2)

add_executable(ndgi_cli ndgi_cli.cc)
target_include_directories(ndgi_cli PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)
target_link_libraries(ndgi_cli PRIVATE ndgi trit_lib ternary_search_tree)
target_compile_options(ndgi_cli PRIVATE -Wall -Wextra -Werror -O2)
