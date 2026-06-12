@rest @agent @P0
Feature: Agent CRUD via REST
  Background:
    Given I am logged in with a session

  @AGENT-REST-001
  Scenario: Create a new agent with title and system role
    When I create a REST agent named "E2E REST CRUD Agent" with system role "You answer briefly."
    And I request the created REST agent
    Then the REST agent should have title "E2E REST CRUD Agent" and system role "You answer briefly."

  @AGENT-REST-002
  Scenario: Rename an agent
    When I create a REST agent named "E2E REST Rename Agent" with system role "Original role"
    And I rename the created REST agent to "E2E REST Renamed Agent"
    And I request the created REST agent
    Then the REST agent should have title "E2E REST Renamed Agent"

  @AGENT-REST-003
  Scenario: Duplicate an agent
    When I create a REST agent named "E2E REST Duplicate Agent" with system role "Duplicate role"
    And I duplicate the created REST agent as "E2E REST Duplicate Agent Copy"
    And I request the duplicated REST agent
    Then the duplicated REST agent should have title "E2E REST Duplicate Agent Copy"

  @AGENT-REST-004
  Scenario: Delete an agent
    When I create a REST agent named "E2E REST Delete Agent" with system role "Delete role"
    And I delete the created REST agent
    And I request the created REST agent
    Then the REST agent should not exist
