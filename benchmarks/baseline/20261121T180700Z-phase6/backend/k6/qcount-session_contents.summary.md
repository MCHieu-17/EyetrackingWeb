# k6 summary

scenario: session_contents

- http_req_waiting: min=4.066, med=15.789, max=20.645, p(90)=18.592, p(95)=19.550, p(99)=20.426, avg=13.901
- http_req_blocked: avg=0.016, min=0.004, med=0.011, max=0.107, p(90)=0.014, p(95)=0.020, p(99)=0.089
- iterations: count=20.000, rate=4.648
- http_req_sending: p(90)=0.054, p(95)=0.065, p(99)=0.070, avg=0.045, min=0.017, med=0.045, max=0.071
- http_req_duration: min=4.138, med=15.975, max=20.799, p(90)=18.746, p(95)=19.676, p(99)=20.574, avg=14.037
- http_req_failed: rate=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.077, p(90)=0.000, p(95)=0.004, p(99)=0.062, avg=0.004
- http_req_receiving: p(95)=0.164, p(99)=0.168, avg=0.091, min=0.027, med=0.092, max=0.169, p(90)=0.152
- http_req_duration{expected_response:true}: p(99)=20.574, avg=14.037, min=4.138, med=15.975, max=20.799, p(90)=18.746, p(95)=19.676
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
