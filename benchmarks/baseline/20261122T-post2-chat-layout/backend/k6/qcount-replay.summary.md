# k6 summary

scenario: replay

- http_req_connecting: med=0.000, max=0.088, p(90)=0.000, p(95)=0.004, p(99)=0.071, avg=0.004, min=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: avg=0.018, min=0.004, med=0.011, max=0.118, p(90)=0.028, p(95)=0.046, p(99)=0.104
- http_req_sending: med=0.044, max=0.085, p(90)=0.054, p(95)=0.060, p(99)=0.080, avg=0.045, min=0.013
- http_req_waiting: avg=8.929, min=2.823, med=8.661, max=13.310, p(90)=11.931, p(95)=12.141, p(99)=13.076
- http_req_duration: min=2.907, med=9.037, max=13.734, p(90)=12.132, p(95)=12.321, p(99)=13.452, avg=9.140
- http_req_duration{expected_response:true}: p(99)=13.452, avg=9.140, min=2.907, med=9.037, max=13.734, p(90)=12.132, p(95)=12.321
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.754
- http_req_receiving: min=0.030, med=0.142, max=0.512, p(90)=0.358, p(95)=0.382, p(99)=0.486, avg=0.167
- http_req_failed: rate=0.000
