@rest @session @P0
Feature: Session Management via REST
  Background:
    Given I am logged in with a session

  @SESSION-REST-001
  Scenario: Starting a chat creates a new session
    When I create a REST session with agent named "E2E REST Session Agent"
    And I request the created REST session
    Then the REST session should exist

  @SESSION-REST-002
  Scenario: Session list shows recent conversations
    When I create a REST session with agent named "E2E REST Listed Session Agent"
    And I request the REST session list
    Then the REST session list should include the created session

  @SESSION-REST-003
  Scenario: Delete session removes it from list
    When I create a REST session with agent named "E2E REST Deleted Session Agent"
    And I delete the created REST session
    And I request the REST session list
    Then the REST session list should not include the created session

  @SESSION-REST-004
  Scenario: Sessions are grouped
    When I create a REST session group named "E2E REST Session Group"
    And I create a REST session with agent named "E2E REST Grouped Session Agent" in the created session group
    And I request the REST grouped sessions
    Then the REST grouped sessions should include the created session group
