9/7
- Using Typer object for CLI interface. 
- upon "lean init" a config file will be created
    - there exists a function in paths.py that will check the creation of the config file for 
    status of initalization
LEFT OFF:
- building the config.json schema and decided on using pydantic for object validation.

9/15
- config file set up with pydantic. 
    - created default_config()
        - blank LeanConfig() object returned
    - created save_config()
        - writes config object to .lean/config.json path
    - created merge_overrides
        - takes LeanConfig obj and a dict of changed config values
        - merges together with default/existing config
        - returns the updated LeanConfig object
    - created init_project()
        - merges default config with potential overrides
        - writes to .lean/config.json w/ save_config()
LEFT OFF:
- config schema and cli init function should be finished. will need to do small testing segment then continue to next portion of project.

9/25
- altered cli.py init method to be simpler and call the init_project function from config. 
    - the init_project function will call all other methods inside config.py. Good to know for testing
- fixed args in config.py init_project function. 

LEFT OFF: 
- Understanding where and what to test. From my understanding now. I just need to use a test to run init from cli.py and see if all functions are used correctly
    - should be init(cli.py) -> init_project(config.py) -> merge_overrides(config.py) -> save_config(config.py)
    - After this function calling sequence completes I should have a .lean dir inside wherever I called from and it should have a default config.py or an altered config.py depending on if I had changed anything 

9/26
- Completed 3 tests
    - 2 tests in test_cli.py
        - one testing all overrides in a "init --provider openai..." etc
        - one testing one override. "init --model llama3"
    - 1 test in test_init.py 
        - verifies init_project generates a valid .lean dir and valid config.json file
- added error handling to the main init in cli.py
    - since its top layer itll handle errors anywhere in the init process but it may be troublesome to find them
LEFT OFF:
- I created a doc with all spec up until real LLM involvement. Currentely in claude last chat still. Need to read and refine then start implementation. 


9/28
READABILITY OVER COMPACTNESS
SIMPLISITY OVER COMPLEXITY (most applications)
- Completed query.py
    - logic hub for turning graphify data into useful data for LLM and me
    - BFS_query and Top_nodes query now exist
        - uses adj created in loader and finds neighbor nodes that can be of use to the LLM
    - adapters in query.py such as the format function, create readable data from the adj table and the nodes currently available
- changed Node var into a TypedDict structure in loader.py to achieve method use for dictionaries in the Node structure. 
- added a imitation graph for testing to tests/fixtures/graph.json
- added graph_path to paths.py

LEFT OFF:
- Testing the use of the graph data functions
- current expectation
    graphify runs automatically
    ↓
    raw graph data, usually graph.json
    ↓
    loader.py translates it into nodes and adjacency maps
    ↓
    query.py finds matching nodes and neighbors
    ↓
    formatted context is returned to the LLM
- need to implement the 13 tests and run them to ensure completion of stage 3

9/29
- Completed the stage 3 test suite w/ all them passing
    - not exactly sure what each and every test does but i should review before starting the next session
LEFT OFF:
- Check the test suite for stage 3 for understanding
- start stage 4 and compelte the stage 4 test suite. 


