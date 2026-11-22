# k6 summary

scenario: aoi_summary

- http_req_failed: rate=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_receiving: max=0.867, p(90)=0.502, p(95)=0.670, p(99)=0.867, avg=0.282, min=0.118, med=0.216
- http_req_waiting: p(90)=223.178, p(95)=230.267, p(99)=244.822, avg=187.933, min=166.581, med=183.611, max=249.043
- http_req_duration: min=166.801, med=183.969, max=249.419, p(90)=223.715, p(95)=230.579, p(99)=245.111, avg=188.277
- http_req_blocked: p(95)=0.023, p(99)=0.102, avg=0.015, min=0.003, med=0.011, max=0.116, p(90)=0.014
- http_req_duration{expected_response:true}: avg=188.277, min=166.801, med=183.969, max=249.419, p(90)=223.715, p(95)=230.579, p(99)=245.111
- http_req_connecting: p(99)=0.074, avg=0.003, min=0.000, med=0.000, max=0.083, p(90)=0.000, p(95)=0.000
- http_req_sending: avg=0.061, min=0.015, med=0.052, max=0.426, p(90)=0.073, p(95)=0.096, p(99)=0.262
- iterations: count=52.000, rate=5.133
- vus: min=2.000, max=2.000
