@rest @chat @P0
Feature: Chat Runtime via REST
  Background:
    Given I am logged in with a session

  @CHAT-REST-001
  Scenario: Server chat creates user and assistant messages
    When I create a REST chat runtime conversation named "E2E REST Chat"
    And I send a REST server chat message "Hello REST runtime"
    And I request REST messages for the chat runtime topic
    Then the REST chat runtime messages should include "Hello REST runtime"
    And the REST chat runtime should include a loading assistant message

  @CHAT-REST-002
  Scenario: Agent runtime validates required model runtime config
    When I request a REST agent runtime operation without model config
    Then the REST agent runtime request should fail with status 400
