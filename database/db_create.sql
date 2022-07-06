CREATE DATABASE IF NOT EXISTS crypto;
USE crypto;

DROP TABLE IF EXISTS tokens;
CREATE TABLE IF NOT EXISTS tokens (
    -- INSERTED by recorder.py
	pair VARCHAR(42), 
    token_name VARCHAR(200),
    recorder_time DATETIME, 
    main_token VARCHAR(42), 
    transaction_hash VARCHAR(66), 
    creator_address VARCHAR(42), 
    block_hash VARCHAR(66), 
    block_number INT,
    log_index INT,
    transactionIndex INT,
    unknown VARCHAR(42),
    
    -- UPDATED by monitor_early.py
    early_status VARCHAR(15),
    early_status_cause VARCHAR(100),
    early_monitor_time DATETIME,
    
    -- UPDATED by monitor_mature.py or liquidity_check.py
    mature_status VARCHAR(15), 
	mature_status_cause VARCHAR(100),
	mature_monitor_time DATETIME,
    -- UPDATED by monitor_mature.py
    liquidity FLOAT,
    lock_expiry DATETIME,
	lock_block INT,
	
    -- UPDATED by check_google_count.py
    google_results_count INT,
    
    PRIMARY KEY (pair)
);

-- insert 1 good token
INSERT INTO tokens values (
    '0xd16E57367519eAD068CfcDe7CF3b95A03994ACE7','MetaGear Token','2022-01-21 14:00:10',
    '0xb4404DaB7C0eC48b428Cf37DeC7fb628bcC41B36',
    '0x29d6fea58d2f2c11f6194c4fb00c980aff8c4ab2178b8c790244d0aa6698c50e',
    '0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73',
    '0xd00d8b4ef30e9dc21c6969ab1e5b7ec1453cd650ebf4d0c04270bebb5dd82a95',
    14560557,1039,592,'701321','ok',null,'2022-02-04 09:14:19','good',
    'lock no transactions in 100 blocks','2022-02-06 12:06:14',20,null,null,644
);
