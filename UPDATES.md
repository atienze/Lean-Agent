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

