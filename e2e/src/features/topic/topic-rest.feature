@rest @topic @P0
Feature: Topic Management via REST
  Background:
    Given I am logged in with a session

  @TOPIC-REST-001
  Scenario: Create a topic in a session
    When I create a REST topic named "E2E REST Topic"
    And I request REST topics for the created session
    Then the REST topic list should include the created topic

  @TOPIC-REST-002
  Scenario: Rename topic
    When I create a REST topic named "E2E REST Topic To Rename"
    And I rename the created REST topic to "E2E REST Topic Renamed"
    And I request the created REST topic
    Then the REST topic should have title "E2E REST Topic Renamed"

  @TOPIC-REST-003
  Scenario: Favorite topic
    When I create a REST topic named "E2E REST Topic To Favorite"
    And I favorite the created REST topic
    And I request the created REST topic
    Then the REST topic should be marked favorite

  @TOPIC-REST-004
  Scenario: Delete topic
    When I create a REST topic named "E2E REST Topic To Delete"
    And I delete the created REST topic
    And I request REST topics for the created session
    Then the REST topic list should not include the created topic
