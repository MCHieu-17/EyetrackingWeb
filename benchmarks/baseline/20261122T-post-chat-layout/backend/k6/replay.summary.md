# k6 summary

scenario: replay

- http_req_sending: p(99)=0.108, avg=0.044, min=0.009, med=0.043, max=0.178, p(90)=0.054, p(95)=0.063
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(99)=36.432, avg=10.027, min=2.703, med=10.100, max=36.472, p(90)=12.788, p(95)=14.059
- http_req_blocked: max=0.114, p(90)=0.014, p(95)=0.017, p(99)=0.093, avg=0.014, min=0.003, med=0.011
- http_req_duration: p(99)=36.432, avg=10.027, min=2.703, med=10.100, max=36.472, p(90)=12.788, p(95)=14.059
- vus: min=2.000, max=2.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_receiving: med=0.153, max=0.575, p(90)=0.338, p(95)=0.399, p(99)=0.471, avg=0.172, min=0.024
- iterations: count=96.000, rate=9.476
- http_req_connecting: min=0.000, med=0.000, max=0.084, p(90)=0.000, p(95)=0.000, p(99)=0.066, avg=0.002
- http_req_waiting: max=36.293, p(90)=12.569, p(95)=13.846, p(99)=36.255, avg=9.811, min=2.630, med=9.746
