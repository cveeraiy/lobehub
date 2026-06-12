@rest @home @P0
Feature: Home and Navigation via REST
  Background:
    Given I am logged in with a session

  @HOME-REST-001
  Scenario: Sidebar loads agent list
    When I request the REST home sidebar
    Then the REST home sidebar should contain sidebar sections

  @HOME-REST-002
  Scenario: Creating a new agent adds it to the sidebar
    When I create a REST home agent named "E2E REST Agent"
    And I request the REST home sidebar
    Then the REST home sidebar should include the created agent

  @HOME-REST-003
  Scenario: Moving an agent to a group updates the sidebar group
    When I create a REST home agent named "E2E Grouped REST Agent"
    And I create a REST home group named "E2E REST Group"
    And I move the created REST home agent into the created group
    And I request the REST home sidebar
    Then the REST home sidebar group should include the created agent

  @HOME-REST-004
  Scenario: Recent conversations load
    When I create a REST home agent named "E2E Recent REST Agent"
    And I create a REST recent topic named "E2E REST Recent Topic"
    And I request REST recents with limit 10
    Then REST recents should include the created topic
