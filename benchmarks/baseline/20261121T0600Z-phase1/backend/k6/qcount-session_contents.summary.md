# k6 summary

scenario: session_contents

- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_receiving: med=0.072, max=0.247, p(90)=0.142, p(95)=0.212, p(99)=0.240, avg=0.086, min=0.028
- http_req_connecting: p(99)=0.061, avg=0.004, min=0.000, med=0.000, max=0.075, p(90)=0.000, p(95)=0.004
- iterations: count=20.000, rate=4.534
- http_req_duration{expected_response:true}: p(90)=27.125, p(95)=27.356, p(99)=28.915, avg=19.503, min=5.738, med=22.576, max=29.305
- http_req_blocked: avg=0.016, min=0.010, med=0.011, max=0.107, p(90)=0.015, p(95)=0.021, p(99)=0.090
- http_req_waiting: med=22.437, max=29.126, p(90)=26.999, p(95)=27.160, p(99)=28.733, avg=19.365, min=5.648
- http_req_duration: p(95)=27.356, p(99)=28.915, avg=19.503, min=5.738, med=22.576, max=29.305, p(90)=27.125
- http_req_sending: p(95)=0.069, p(99)=0.120, avg=0.052, min=0.037, med=0.045, max=0.133, p(90)=0.063
