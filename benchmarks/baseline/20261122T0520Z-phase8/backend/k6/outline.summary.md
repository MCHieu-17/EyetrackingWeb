# k6 summary

scenario: outline

- iterations: count=238.000, rate=23.634
- http_req_duration: p(90)=15.237, p(95)=15.652, p(99)=39.939, avg=10.341, min=2.211, med=9.861, max=50.624
- http_req_blocked: p(90)=0.014, p(95)=0.021, p(99)=0.121, avg=0.013, min=0.002, med=0.011, max=0.128
- http_req_failed: rate=0.000
- http_req_sending: p(95)=0.056, p(99)=0.079, avg=0.038, min=0.006, med=0.039, max=0.104, p(90)=0.048
- http_req_waiting: p(90)=15.060, p(95)=15.284, p(99)=39.852, avg=10.151, min=2.147, med=9.639, max=50.543
- http_req_duration{expected_response:true}: p(90)=15.237, p(95)=15.652, p(99)=39.939, avg=10.341, min=2.211, med=9.861, max=50.624
- http_req_connecting: med=0.000, max=0.094, p(90)=0.000, p(95)=0.000, p(99)=0.092, avg=0.002, min=0.000
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: p(90)=0.272, p(95)=0.314, p(99)=0.581, avg=0.152, min=0.013, med=0.130, max=2.531
- vus: min=5.000, max=5.000
