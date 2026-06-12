@rest @message @P0
Feature: Message Management via REST
  Background:
    Given I am logged in with a session

  @MESSAGE-REST-001
  Scenario: Create and load messages
    When I create a REST message conversation named "E2E REST Message"
    And I request REST messages for the created topic
    Then the REST message list should include "Hello from REST"

  @MESSAGE-REST-002
  Scenario: Edit a message
    When I create a REST message conversation named "E2E REST Message To Edit"
    And I edit the created REST message to "Edited from REST"
    And I request REST messages for the created topic
    Then the REST message list should include "Edited from REST"

  @MESSAGE-REST-003
  Scenario: Delete a message
    When I create a REST message conversation named "E2E REST Message To Delete"
    And I delete the created REST message
    And I request REST messages for the created topic
    Then the REST message list should not include "Hello from REST"

  @MESSAGE-REST-004
  Scenario: Paginate messages
    When I create a REST message conversation named "E2E REST Message Pagination"
    And I create 3 more REST messages
    And I request the first 2 REST messages for the created topic
    Then the REST message page should contain 2 messages
